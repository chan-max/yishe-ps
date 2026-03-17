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
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'


def is_photoshop_running() -> bool:
    """检查 Photoshop 是否正在运行。"""
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            proc_name = proc.info.get("name") or ""
            if "Photoshop" in proc_name:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False


def _normalize_photoshop_exe(candidate: str | Path | None) -> Optional[Path]:
    """将候选路径归一化为 Photoshop.exe 路径。"""
    if not candidate:
        return None

    path = Path(candidate)
    if path.is_file() and path.name.lower() == "photoshop.exe":
        return path

    exe_path = path / "Photoshop.exe"
    if exe_path.exists():
        return exe_path

    return None


def _find_photoshop_from_registry() -> Optional[Path]:
    """从注册表扫描 Photoshop 安装路径。"""
    if os.name != "nt":
        return None

    try:
        import winreg
    except ImportError:
        return None

    root_keys = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    registry_specs = [
        (r"SOFTWARE\Adobe\Photoshop", winreg.KEY_WOW64_64KEY),
        (r"SOFTWARE\Adobe\Photoshop", winreg.KEY_WOW64_32KEY),
        (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Photoshop.exe", 0),
    ]

    discovered_paths: list[Path] = []

    for root_key in root_keys:
        for subkey_path, wow_flag in registry_specs:
            try:
                key = winreg.OpenKey(root_key, subkey_path, 0, winreg.KEY_READ | wow_flag)
            except OSError:
                continue

            try:
                if subkey_path.endswith(r"App Paths\Photoshop.exe"):
                    try:
                        app_path = winreg.QueryValueEx(key, None)[0]
                    except OSError:
                        app_path = None
                    exe_path = _normalize_photoshop_exe(app_path)
                    if exe_path:
                        discovered_paths.append(exe_path)
                    continue

                index = 0
                while True:
                    try:
                        version = winreg.EnumKey(key, index)
                    except OSError:
                        break
                    index += 1

                    try:
                        version_key = winreg.OpenKey(key, version)
                    except OSError:
                        continue

                    for value_name in ("ApplicationPath", "ApplicationFolder"):
                        try:
                            raw_path = winreg.QueryValueEx(version_key, value_name)[0]
                        except OSError:
                            continue
                        exe_path = _normalize_photoshop_exe(raw_path)
                        if exe_path:
                            discovered_paths.append(exe_path)
                            break
            finally:
                winreg.CloseKey(key)

    if not discovered_paths:
        return None

    return sorted(set(discovered_paths), key=lambda p: str(p), reverse=True)[0]


def find_photoshop_executable() -> Optional[Path]:
    """查找 Photoshop 可执行文件路径（Windows）。"""
    possible_paths = []

    for base_dir in ("C:/Program Files/Adobe", "C:/Program Files (x86)/Adobe"):
        for version in (2026, 2025, 2024, 2023, 2022, 2021):
            possible_paths.append(Path(f"{base_dir}/Adobe Photoshop {version}/Photoshop.exe"))
        for cc_version in (2020, 2019, 2018):
            possible_paths.append(Path(f"{base_dir}/Adobe Photoshop CC {cc_version}/Photoshop.exe"))

    for path in possible_paths:
        if path.exists():
            return path

    return _find_photoshop_from_registry()


def _wait_for_photoshop_ready(timeout: int, extra_com_wait: int = 5) -> bool:
    """等待 Photoshop 进程出现并给 COM 初始化留出时间。"""
    print(f"等待 Photoshop 启动（最多 {timeout} 秒）...")
    for _ in range(timeout):
        time.sleep(1)
        if is_photoshop_running():
            print("✅ Photoshop 启动成功")
            print("等待 Photoshop COM 接口初始化...")
            time.sleep(extra_com_wait)
            return True
    print("❌ Photoshop 启动超时")
    return False


def _start_photoshop_via_com(timeout: int) -> bool:
    """使用 COM 方式兜底启动 Photoshop。"""
    print("尝试使用 Photoshop COM 接口启动...")
    try:
        from photoshop import Session

        session = Session()
        _ = session.app
        return _wait_for_photoshop_ready(timeout=max(5, min(timeout, 15)), extra_com_wait=3)
    except Exception as e:
        print(f"❌ COM 方式启动 Photoshop 失败: {e}")
        return False


def start_photoshop(timeout: int = 30) -> bool:
    """自动启动 Photoshop（如果未运行）。

    Args:
        timeout: 等待 Photoshop 启动的超时时间（秒），默认 30 秒

    Returns:
        如果成功启动或已运行返回 True，否则返回 False
    """
    if is_photoshop_running():
        print("✅ Photoshop 已在运行")
        return True

    print("正在查找 Photoshop 安装路径...")
    ps_exe = find_photoshop_executable()

    if ps_exe:
        print(f"找到 Photoshop: {ps_exe}")
        print("正在启动 Photoshop...")
        try:
            subprocess.Popen(
                [str(ps_exe)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0,
            )
            if _wait_for_photoshop_ready(timeout):
                return True
            print("⚠️ 通过可执行文件启动未成功，尝试 COM 方式兜底...")
        except Exception as e:
            print(f"❌ 启动 Photoshop 失败: {e}")
            print("⚠️ 将尝试通过 COM 方式启动 Photoshop...")
    else:
        print("⚠️ 未找到 Photoshop 安装路径，将尝试使用 COM 方式启动")

    return _start_photoshop_via_com(timeout)


def ensure_photoshop_running(auto_start: bool = True, timeout: int = 30) -> bool:
    """确保 Photoshop 正在运行，如果没有运行则自动启动。"""
    if is_photoshop_running():
        return True

    if not auto_start:
        print("❌ Photoshop 未运行，且 auto_start=False，请手动启动 Photoshop")
        return False

    return start_photoshop(timeout)


def close_photoshop_process(force: bool = False) -> bool:
    """关闭 Photoshop 进程。"""
    found = False
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            proc_name = proc.info.get("name") or ""
            if "Photoshop" in proc_name:
                found = True
                if force:
                    proc.kill()
                else:
                    proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not found:
        return True

    if not force:
        try:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    proc_name = proc.info.get("name") or ""
                    if "Photoshop" in proc_name:
                        proc.wait(timeout=10)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.TimeoutExpired):
                    continue
        except Exception:
            pass

    return True


def restart_photoshop(timeout: int = 30) -> bool:
    """重启 Photoshop。"""
    if is_photoshop_running():
        print("正在关闭 Photoshop...")
        close_photoshop_process(force=False)
        for _ in range(10):
            time.sleep(1)
            if not is_photoshop_running():
                break

    print("正在启动 Photoshop...")
    return start_photoshop(timeout)


def create_photoshop_session(max_retries: int = 5, retry_delay: int = 2):
    """创建 Photoshop Session，带重试逻辑。"""
    from photoshop import Session

    if not ensure_photoshop_running(auto_start=True):
        raise RuntimeError("无法启动 Photoshop，请确保 Photoshop 已正确安装")

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
            if "无效的类字符串" in error_msg or "WinError -2147221005" in error_msg or "WinError 259" in error_msg:
                if attempt < max_retries - 1:
                    print(f"COM 接口尚未就绪，等待 {current_delay} 秒后重试...")
                    time.sleep(current_delay)
                    current_delay += 1
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
                raise

    if session is None:
        raise RuntimeError(f"无法创建 Photoshop Session: {last_error}")

    return session
