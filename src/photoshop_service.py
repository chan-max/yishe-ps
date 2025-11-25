from __future__ import annotations

import gc
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil
from PIL import Image
from photoshop import Session
from photoshop.api import ActionDescriptor, ActionReference
from photoshop.api.enumerations import DialogModes


def _resize_image_in_tiles(img: Image.Image, target_size: tuple[int, int], tile_size: int) -> Image.Image:
    """参考 ps_client 中的实现，分块缩放大尺寸图片，降低内存占用。"""
    orig_width, orig_height = img.size
    target_width, target_height = target_size
    scale_x = target_width / orig_width
    scale_y = target_height / orig_height

    resized_img = Image.new(img.mode, (target_width, target_height))
    for top in range(0, orig_height, tile_size):
        bottom = min(top + tile_size, orig_height)
        for left in range(0, orig_width, tile_size):
            right = min(left + tile_size, orig_width)
            box = (left, top, right, bottom)
            tile = img.crop(box)

            out_left = int(left * scale_x)
            out_top = int(top * scale_y)
            out_right = int(right * scale_x)
            out_bottom = int(bottom * scale_y)

            tile_resized = tile.resize((out_right - out_left, out_bottom - out_top), Image.LANCZOS)
            resized_img.paste(tile_resized, (out_left, out_top))

            tile.close()
            del tile_resized
    return resized_img


@dataclass
class PhotoshopJob:
    """描述一次 PSD 套图任务所需的输入。"""

    png_path: Path
    psd_path: Path
    export_dir: Path
    artboard_name: Optional[str] = None

    def validate(self) -> None:
        if not self.png_path.exists():
            raise FileNotFoundError(f"替换图片不存在：{self.png_path}")
        if not self.psd_path.exists():
            raise FileNotFoundError(f"PSD 模板不存在：{self.psd_path}")
        if self.export_dir.suffix:
            raise ValueError("export_dir 必须是目录路径")
        self.export_dir.mkdir(parents=True, exist_ok=True)


class PhotoshopService:
    """封装 Photoshop Session 生命周期与智能对象替换流程。"""

    def __init__(self, tile_size: int = 512):
        self.tile_size = tile_size

    @staticmethod
    def close_photoshop_process() -> None:
        """关闭残留的 Photoshop 进程，以免影响后续任务。"""
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                if "Photoshop" in proc.info["name"]:
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def replace_and_export(self, job: PhotoshopJob) -> Path:
        """执行一次套图流程并返回导出的 PNG 路径。"""
        job.validate()

        with Session() as session:
            app = session.app
            doc = app.open(str(job.psd_path))

            target_layer = self._pick_layer(doc, job.artboard_name)
            self._replace_layer_contents(session, doc, target_layer, job.png_path, job.export_dir)

            export_path = job.export_dir / f"{job.png_path.stem}_export.png"
            options = session.ExportOptionsSaveForWeb()
            doc.exportDocument(str(export_path), exportAs=session.ExportType.SaveForWeb, options=options)
            doc.close()

        gc.collect()
        return export_path

    def _pick_layer(self, doc, artboard_name: Optional[str]):
        if artboard_name:
            for artboard in doc.layerSets:
                if artboard.name == artboard_name:
                    artboard.visible = True
                    if artboard.layers:
                        return artboard.layers[0]
                    return artboard
            raise ValueError(f"未找到名为 {artboard_name} 的图层组/画板")
        return doc.activeLayer or doc.layers[0]

    def _replace_layer_contents(self, session: Session, doc, layer, png_path: Path, export_dir: Path) -> None:
        doc.activeLayer = layer
        string_id = session.app.stringIDToTypeID

        edit_contents_id = string_id("placedLayerEditContents")
        placed_layer_id = string_id("placedLayer")
        ordinal_id = string_id("ordinal")
        target_enum_id = string_id("targetEnum")

        ref = ActionReference()
        ref.putEnumerated(placed_layer_id, ordinal_id, target_enum_id)

        desc = ActionDescriptor()
        desc.putReference(string_id("null"), ref)

        session.app.executeAction(edit_contents_id, desc, DialogModes.DisplayNoDialogs)

        smart_doc = session.active_document
        resized_path = self._prepare_resized_image(png_path, smart_doc, export_dir)

        place_desc = ActionDescriptor()
        place_desc.putPath(string_id("null"), str(resized_path))
        place_desc.putBoolean(string_id("antiAlias"), True)
        session.app.executeAction(string_id("placeEvent"), place_desc, DialogModes.DisplayNoDialogs)

        smart_doc.save()
        smart_doc.close()
        gc.collect()

    def _prepare_resized_image(self, png_path: Path, smart_doc, export_dir: Path) -> Path:
        with Image.open(png_path) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            target_width = int(smart_doc.width)
            target_height = int(smart_doc.height)
            resized_img = _resize_image_in_tiles(img, (target_width, target_height), self.tile_size)

            resized_path = export_dir / f"{png_path.stem}_resized{png_path.suffix}"
            resized_img.save(resized_path, dpi=(int(smart_doc.resolution), int(smart_doc.resolution)))

        resized_img.close()
        gc.collect()
        return resized_path

