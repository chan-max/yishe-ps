from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from .photoshop_service import PhotoshopJob, PhotoshopService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于 photoshop-python-api 的通用示例")
    parser.add_argument("--png", required=True, help="待替换的 PNG/JPG 路径")
    parser.add_argument("--psd", required=True, help="PSD 模板路径")
    parser.add_argument("--output", required=True, help="导出目录")
    parser.add_argument("--artboard", help="可选：指定画板/图层组名称")
    parser.add_argument("--tile-size", type=int, default=512, help="缩放分块尺寸，默认 512")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    service = PhotoshopService(tile_size=args.tile_size)
    job = PhotoshopJob(
        png_path=Path(args.png),
        psd_path=Path(args.psd),
        export_dir=Path(args.output),
        artboard_name=args.artboard,
    )

    try:
        export_path = service.replace_and_export(job)
        print(f"✅ 已导出：{export_path}")
    except Exception as exc:
        service.close_photoshop_process()
        raise SystemExit(f"❌ 处理失败：{exc}") from exc


if __name__ == "__main__":
    main()

