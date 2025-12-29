"""
权限检查工具模块
"""
import os
from pathlib import Path


def check_write_permission(path: Path) -> tuple[bool, str]:
    """
    检查路径的写入权限
    
    Args:
        path: 要检查的路径（文件或目录）
    
    Returns:
        (是否有权限, 错误信息)
    """
    try:
        # 如果是文件，检查父目录
        check_path = path.parent if path.suffix else path
        
        # 检查目录是否存在，如果不存在尝试创建
        if not check_path.exists():
            try:
                check_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return False, f"没有权限创建目录: {check_path}"
        
        # 检查是否有写入权限
        if not os.access(check_path, os.W_OK):
            return False, f"没有写入权限: {check_path}"
        
        # 如果是文件且已存在，检查是否可以写入
        if path.exists() and path.is_file():
            if not os.access(path, os.W_OK):
                return False, f"文件已存在但没有写入权限: {path}"
        
        return True, ""
    except Exception as e:
        return False, f"检查权限时出错: {e}"


def check_photoshop_permissions() -> tuple[bool, str]:
    """
    检查 Photoshop 相关的权限
    
    Returns:
        (是否有权限, 错误信息)
    """
    try:
        # 检查临时目录权限（PS 可能需要）
        temp_dir = Path(os.environ.get('TEMP', os.environ.get('TMP', '.')))
        if not os.access(temp_dir, os.W_OK):
            return False, f"临时目录没有写入权限: {temp_dir}"
        return True, ""
    except Exception as e:
        return False, f"检查 Photoshop 权限时出错: {e}"

