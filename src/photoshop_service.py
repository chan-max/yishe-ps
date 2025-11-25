from __future__ import annotations

import gc
from pathlib import Path
from typing import Optional

from PIL import Image
from photoshop import Session
from photoshop.api import ActionDescriptor, ActionReference
from photoshop.api.enumerations import DialogModes

from .utils import resize_image_in_tiles, validate_job_inputs


def pick_layer(doc, artboard_name: Optional[str]):
    """选择目标图层，如果指定了画板名称则查找对应画板。"""
    if artboard_name:
        for artboard in doc.layerSets:
            if artboard.name == artboard_name:
                artboard.visible = True
                if artboard.layers:
                    return artboard.layers[0]
                return artboard
        raise ValueError(f"未找到名为 {artboard_name} 的图层组/画板")
    return doc.activeLayer or doc.layers[0]


def _prepare_resized_image(png_path: Path, smart_doc, export_dir: Path, tile_size: int) -> Path:
    """准备缩放后的图片文件。"""
    with Image.open(png_path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        target_width = int(smart_doc.width)
        target_height = int(smart_doc.height)
        resized_img = resize_image_in_tiles(img, (target_width, target_height), tile_size)

        resized_path = export_dir / f"{png_path.stem}_resized{png_path.suffix}"
        resized_img.save(resized_path, dpi=(int(smart_doc.resolution), int(smart_doc.resolution)))

    resized_img.close()
    gc.collect()
    return resized_path


def replace_layer_contents(session: Session, doc, layer, png_path: Path, export_dir: Path, tile_size: int) -> None:
    """替换图层中的智能对象内容。"""
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
    resized_path = _prepare_resized_image(png_path, smart_doc, export_dir, tile_size)

    place_desc = ActionDescriptor()
    place_desc.putPath(string_id("null"), str(resized_path))
    place_desc.putBoolean(string_id("antiAlias"), True)
    session.app.executeAction(string_id("placeEvent"), place_desc, DialogModes.DisplayNoDialogs)

    smart_doc.save()
    smart_doc.close()
    gc.collect()


def replace_and_export(
    png_path: Path,
    psd_path: Path,
    export_dir: Path,
    artboard_name: Optional[str] = None,
    tile_size: int = 512,
) -> Path:
    """执行一次套图流程并返回导出的 PNG 路径。
    
    Args:
        png_path: 待替换的图片路径
        psd_path: PSD 模板路径
        export_dir: 导出目录
        artboard_name: 可选的画板/图层组名称
        tile_size: 缩放分块尺寸，默认 512
        
    Returns:
        导出的 PNG 文件路径
    """
    validate_job_inputs(png_path, psd_path, export_dir)

    with Session() as session:
        app = session.app
        doc = app.open(str(psd_path))

        target_layer = pick_layer(doc, artboard_name)
        replace_layer_contents(session, doc, target_layer, png_path, export_dir, tile_size)

        export_path = export_dir / f"{png_path.stem}_export.png"
        options = session.ExportOptionsSaveForWeb()
        doc.exportDocument(str(export_path), exportAs=session.ExportType.SaveForWeb, options=options)
        doc.close()

    gc.collect()
    return export_path

