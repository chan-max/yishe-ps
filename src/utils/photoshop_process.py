"""Photoshop 进程管理相关的工具函数。"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import psutil


def is_photoshop_running() -> bool:
    """检查 Photoshop 是否正在运行。"""
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            if "Photoshop" in proc.info["name"]:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False


def find_photoshop_executable() -> Optional[Path]:
    """查找 Photoshop 可执行文件路径（Windows）。"""
    # 常见的 Photoshop 安装路径
    possible_paths = [
        Path("C:/Program Files/Adobe/Adobe Photoshop 2024/Photoshop.exe"),
        Path("C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe"),
        Path("C:/Program Files/Adobe/Adobe Photoshop 2022/Photoshop.exe"),
        Path("C:/Program Files/Adobe/Adobe Photoshop 2021/Photoshop.exe"),
        Path("C:/Program Files/Adobe/Adobe Photoshop CC 2019/Photoshop.exe"),
        Path("C:/Program Files/Adobe/Adobe Photoshop CC 2018/Photoshop.exe"),
        # 32位系统路径
        Path("C:/Program Files (x86)/Adobe/Adobe Photoshop 2024/Photoshop.exe"),
        Path("C:/Program Files (x86)/Adobe/Adobe Photoshop 2023/Photoshop.exe"),
        Path("C:/Program Files (x86)/Adobe/Adobe Photoshop 2022/Photoshop.exe"),
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # 尝试从注册表查找（仅 Windows）
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Adobe\Photoshop",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )
            version = winreg.EnumKey(key, 0)
            version_key = winreg.OpenKey(key, version)
            install_path = winreg.QueryValueEx(version_key, "ApplicationPath")[0]
            ps_path = Path(install_path) / "Photoshop.exe"
            if ps_path.exists():
                return ps_path
        except Exception:
            pass
    
    return None


def start_photoshop(timeout: int = 30) -> bool:
    """自动启动 Photoshop（如果未运行）。
    
    Args:
        timeout: 等待 Photoshop 启动的超时时间（秒），默认 30 秒
        
    Returns:
        如果成功启动或已运行返回 True，否则返回 False
    """
    # 检查是否已经运行
    if is_photoshop_running():
        print("✅ Photoshop 已在运行")
        return True
    
    print("正在查找 Photoshop 安装路径...")
    ps_exe = find_photoshop_executable()
    
    if not ps_exe:
        print("❌ 未找到 Photoshop 安装路径")
        print("请手动启动 Photoshop 或检查安装路径")
        return False
    
    print(f"找到 Photoshop: {ps_exe}")
    print("正在启动 Photoshop...")
    
    try:
        # 启动 Photoshop（不显示窗口，在后台运行）
        subprocess.Popen(
            [str(ps_exe)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        
        # 等待 Photoshop 启动
        print(f"等待 Photoshop 启动（最多 {timeout} 秒）...")
        for _ in range(timeout):
            time.sleep(1)
            if is_photoshop_running():
                print("✅ Photoshop 启动成功")
                # 额外等待几秒让 Photoshop 完全初始化
                time.sleep(3)
                return True
        
        print("❌ Photoshop 启动超时")
        return False
        
    except Exception as e:
        print(f"❌ 启动 Photoshop 失败: {e}")
        return False


def ensure_photoshop_running(auto_start: bool = True, timeout: int = 30) -> bool:
    """确保 Photoshop 正在运行，如果没有运行则自动启动。
    
    Args:
        auto_start: 如果 Photoshop 未运行是否自动启动，默认 True
        timeout: 启动超时时间（秒），默认 30 秒
        
    Returns:
        如果 Photoshop 正在运行或成功启动返回 True，否则返回 False
    """
    if is_photoshop_running():
        return True
    
    if not auto_start:
        print("❌ Photoshop 未运行，且 auto_start=False，请手动启动 Photoshop")
        return False
    
    return start_photoshop(timeout)


def close_photoshop_process() -> None:
    """关闭残留的 Photoshop 进程，以免影响后续任务。"""
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            if "Photoshop" in proc.info["name"]:
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

