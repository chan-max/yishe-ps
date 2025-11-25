"""Photoshop 连接诊断工具。"""

import os
from typing import Optional


def check_photoshop_com_registration() -> tuple[bool, Optional[str]]:
    """检查 Photoshop COM 接口是否在注册表中正确注册。
    
    Returns:
        (是否注册, 错误信息或 None)
    """
    if os.name != "nt":
        return True, None  # 非 Windows 系统跳过检查
    
    try:
        import winreg
        
        # 检查 Photoshop 注册表项
        possible_keys = [
            r"SOFTWARE\Adobe\Photoshop",
            r"SOFTWARE\Classes\Photoshop.Application",
        ]
        
        found = False
        for key_path in possible_keys:
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    key_path,
                    0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY
                )
                winreg.CloseKey(key)
                found = True
                break
            except FileNotFoundError:
                continue
        
        if not found:
            return False, "Photoshop COM 接口未在注册表中找到。请确保 Photoshop 已正确安装。"
        
        return True, None
        
    except ImportError:
        return True, None  # winreg 不可用时跳过
    except Exception as e:
        return False, f"检查注册表时出错: {e}"


def diagnose_photoshop_connection() -> str:
    """诊断 Photoshop 连接问题并返回诊断信息。"""
    messages = []
    
    # 检查进程是否运行
    from .photoshop_process import is_photoshop_running
    if not is_photoshop_running():
        messages.append("❌ Photoshop 进程未运行")
    else:
        messages.append("✅ Photoshop 进程正在运行")
    
    # 检查注册表
    registered, error = check_photoshop_com_registration()
    if registered:
        messages.append("✅ Photoshop COM 接口已注册")
    else:
        messages.append(f"❌ {error}")
    
    # 检查可执行文件
    from .photoshop_process import find_photoshop_executable
    ps_exe = find_photoshop_executable()
    if ps_exe:
        messages.append(f"✅ 找到 Photoshop 可执行文件: {ps_exe}")
    else:
        messages.append("❌ 未找到 Photoshop 可执行文件")
    
    return "\n".join(messages)

