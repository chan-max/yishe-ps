"""
Photoshop 状态检测服务
用于检测 Photoshop 是否启动、可用，以及连接状态
"""

from typing import Optional, Dict, Any
from datetime import datetime

try:
    from ..utils import (
        is_photoshop_running,
        find_photoshop_executable,
    )
    from ..utils.photoshop_diagnostics import (
        check_photoshop_com_registration,
        diagnose_photoshop_connection
    )
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.utils import (
        is_photoshop_running,
        find_photoshop_executable,
    )
    from src.utils.photoshop_diagnostics import (
        check_photoshop_com_registration,
        diagnose_photoshop_connection
    )


def check_photoshop_status(test_connection: bool = False) -> Dict[str, Any]:
    """
    检测 Photoshop 状态和可用性
    
    Args:
        test_connection: 是否测试 Photoshop COM 连接（需要实际连接PS，可能较慢）
    
    Returns:
        包含状态信息的字典：
        - is_running: bool - Photoshop 进程是否运行
        - is_available: bool - Photoshop 是否可用（运行且可连接）
        - executable_path: Optional[str] - Photoshop 可执行文件路径
        - com_registered: bool - COM 接口是否注册
        - connection_test: Optional[Dict] - 连接测试结果（如果 test_connection=True）
        - diagnostics: str - 诊断信息
        - timestamp: str - 检测时间戳
    """
    result: Dict[str, Any] = {
        "is_running": False,
        "is_available": False,
        "executable_path": None,
        "com_registered": False,
        "connection_test": None,
        "diagnostics": "",
        "timestamp": datetime.now().isoformat()
    }
    
    # 1. 检查进程是否运行
    is_running = is_photoshop_running()
    result["is_running"] = is_running
    
    # 2. 查找可执行文件路径
    ps_exe = find_photoshop_executable()
    if ps_exe:
        result["executable_path"] = str(ps_exe)
    
    # 3. 检查 COM 接口注册
    com_registered, com_error = check_photoshop_com_registration()
    result["com_registered"] = com_registered
    
    # 4. 如果 test_connection=True，测试实际连接
    if test_connection:
        connection_result = _test_photoshop_connection()
        result["connection_test"] = connection_result
        # 如果连接测试成功，说明PS可用
        if connection_result.get("success", False):
            result["is_available"] = True
    else:
        # 不测试连接时，只要进程运行且COM注册就认为可用
        result["is_available"] = is_running and com_registered
    
    # 5. 生成诊断信息
    diagnostics = diagnose_photoshop_connection()
    result["diagnostics"] = diagnostics
    
    return result


def _test_photoshop_connection() -> Dict[str, Any]:
    """
    测试 Photoshop COM 连接
    
    Returns:
        连接测试结果字典：
        - success: bool - 是否成功连接
        - error: Optional[str] - 错误信息（如果失败）
        - version: Optional[str] - Photoshop 版本（如果成功）
    """
    result: Dict[str, Any] = {
        "success": False,
        "error": None,
        "version": None
    }
    
    try:
        # 尝试创建 Photoshop Session 来测试连接
        from photoshop import Session
        
        with Session() as session:
            # 尝试获取 Photoshop 版本信息
            try:
                app = session.app
                # 尝试获取版本（如果API支持）
                if hasattr(app, 'version'):
                    result["version"] = str(app.version)
                result["success"] = True
            except Exception as e:
                result["error"] = f"无法获取 Photoshop 信息: {str(e)}"
                result["success"] = False
                
    except ImportError:
        result["error"] = "photoshop 库未安装或导入失败"
        result["success"] = False
    except Exception as e:
        error_msg = str(e)
        # 常见错误类型
        if "COM" in error_msg or "connection" in error_msg.lower():
            result["error"] = f"COM 连接失败: {error_msg}"
        elif "timeout" in error_msg.lower():
            result["error"] = f"连接超时: {error_msg}"
        else:
            result["error"] = f"连接测试失败: {error_msg}"
        result["success"] = False
    
    return result

