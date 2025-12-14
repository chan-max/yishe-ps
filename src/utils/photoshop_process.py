"""Photoshop 进程管理相关的工具函数。"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Optional

import psutil

# 设置标准输出和错误输出为 UTF-8 编码，避免 Windows GBK 编码问题
if sys.platform == 'win32':
    # 重新配置标准输出和错误输出为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'


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
                # 额外等待更长时间让 Photoshop 完全初始化 COM 接口
                print("等待 Photoshop COM 接口初始化...")
                time.sleep(5)  # 增加等待时间到 5 秒
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


def close_photoshop_process(force: bool = False) -> bool:
    """关闭 Photoshop 进程。
    
    Args:
        force: 是否强制关闭（kill），默认 False（优雅关闭 terminate）
        
    Returns:
        如果成功关闭或未运行返回 True，否则返回 False
    """
    found = False
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            if "Photoshop" in proc.info["name"]:
                found = True
                if force:
                    proc.kill()
                else:
                    proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    if not found:
        return True  # 未运行也算成功
    
    # 等待进程关闭
    if not force:
        try:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    if "Photoshop" in proc.info["name"]:
                        proc.wait(timeout=10)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.TimeoutExpired):
                    continue
        except Exception:
            pass
    
    return True


def restart_photoshop(timeout: int = 30) -> bool:
    """重启 Photoshop。
    
    Args:
        timeout: 启动超时时间（秒），默认 30 秒
        
    Returns:
        如果成功重启返回 True，否则返回 False
    """
    # 先关闭
    if is_photoshop_running():
        print("正在关闭 Photoshop...")
        close_photoshop_process(force=False)
        # 等待进程完全关闭
        for _ in range(10):
            time.sleep(1)
            if not is_photoshop_running():
                break
    
    # 再启动
    print("正在启动 Photoshop...")
    return start_photoshop(timeout)


def create_photoshop_session(max_retries: int = 5, retry_delay: int = 2):
    """创建 Photoshop Session，带重试逻辑。
    
    Args:
        max_retries: 最大重试次数，默认 5
        retry_delay: 初始重试延迟（秒），默认 2，每次重试会增加
        
    Returns:
        Session 对象
        
    Raises:
        RuntimeError: 如果无法创建 Session
    """
    from photoshop import Session
    import time
    
    # 确保 Photoshop 正在运行
    if not ensure_photoshop_running(auto_start=True):
        raise RuntimeError("无法启动 Photoshop，请确保 Photoshop 已正确安装")
    
    # 等待一下，确保 Photoshop COM 接口完全初始化
    print("等待 Photoshop COM 接口初始化...")
    time.sleep(3)
    
    session = None
    last_error = None
    current_delay = retry_delay
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"尝试连接 Photoshop COM 接口 (尝试 {attempt + 1}/{max_retries})...")
            session = Session()
            if attempt > 0:
                print("成功连接到 Photoshop COM 接口")
            break
        except Exception as e:
            last_error = e
            error_msg = str(e)
            # 检查是否是 COM 初始化错误
            if "无效的类字符串" in error_msg or "WinError -2147221005" in error_msg or "WinError 259" in error_msg:
                if attempt < max_retries - 1:
                    print(f"COM 接口尚未就绪，等待 {current_delay} 秒后重试...")
                    time.sleep(current_delay)
                    current_delay += 1  # 每次增加 1 秒
                else:
                    raise RuntimeError(
                        f"无法连接到 Photoshop COM 接口。\n"
                        f"错误: {error_msg}\n"
                        f"请确保：\n"
                        f"1. Photoshop 已正确安装\n"
                        f"2. Photoshop 正在运行\n"
                        f"3. 以管理员权限运行程序"
                    ) from e
            else:
                # 其他错误，直接抛出
                raise
    
    if session is None:
        raise RuntimeError(f"无法创建 Photoshop Session: {last_error}")
    
    return session

