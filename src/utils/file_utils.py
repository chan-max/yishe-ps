"""文件路径和验证相关的工具函数。"""

from pathlib import Path


def validate_job_inputs(png_path: Path, psd_path: Path, export_dir: Path) -> None:
    """验证输入参数的有效性。
    
    Args:
        png_path: 替换图片路径
        psd_path: PSD 模板路径
        export_dir: 导出目录路径
        
    Raises:
        FileNotFoundError: 如果图片或 PSD 文件不存在
        ValueError: 如果 export_dir 不是目录路径
    """
    if not png_path.exists():
        raise FileNotFoundError(f"替换图片不存在：{png_path}")
    if not psd_path.exists():
        raise FileNotFoundError(f"PSD 模板不存在：{psd_path}")
    if export_dir.suffix:
        raise ValueError("export_dir 必须是目录路径")
    export_dir.mkdir(parents=True, exist_ok=True)

