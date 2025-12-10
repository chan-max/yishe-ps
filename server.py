"""
PSD 智能对象替换 API 服务启动入口
项目根目录启动脚本
"""

import sys
import uvicorn
from pathlib import Path

# 添加项目路径
# PyInstaller 打包后的路径处理
if getattr(sys, 'frozen', False):
    # 打包后的可执行文件
    project_root = Path(sys.executable).parent
    # 如果是单文件模式，需要特殊处理
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 临时目录
        project_root = Path(sys._MEIPASS)
else:
    # 开发模式
    project_root = Path(__file__).parent

sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="启动 PSD 智能对象替换 API 服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start_api_server.py                    # 默认端口 1595
  python start_api_server.py --port 8080        # 自定义端口
  python start_api_server.py --reload            # 开发模式（自动重载）
  python start_api_server.py --host 127.0.0.1   # 仅本地访问
        """
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="服务主机地址（默认: localhost，只监听本地回环接口，更安全）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1595,
        help="服务端口（默认: 1595）"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用自动重载（开发模式，代码修改后自动重启）"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="工作进程数（默认: 1，注意：Photoshop 不支持多进程，建议保持为 1）"
    )
    
    args = parser.parse_args()
    
    # 显示启动信息
    print("=" * 70)
    print("PSD 智能对象替换 API 服务")
    print("=" * 70)
    print(f"服务地址: http://{args.host}:{args.port}")
    print(f"API 文档: http://{args.host}:{args.port}/docs")
    print(f"健康检查: http://{args.host}:{args.port}/health")
    print(f"自动重载: {'启用' if args.reload else '禁用'}")
    print(f"工作进程: {args.workers}")
    print("=" * 70)
    print("\n注意事项:")
    print("   - 确保 Photoshop 已安装并可访问")
    print("   - 由于 Photoshop 限制，建议使用单进程模式（workers=1）")
    print("   - 建议以管理员权限运行，避免权限问题")
    print("=" * 70)
    print()
    
    # 警告：多个工作进程可能导致 Photoshop 连接问题
    if args.workers > 1:
        print("警告: 多个工作进程可能导致 Photoshop 连接问题")
        print("   建议使用 workers=1（单进程模式）")
        print()
        # 强制使用单进程
        args.workers = 1
    
    # 启动服务
    try:
        print("\n正在启动服务...\n")
        print("提示: 服务运行中，此窗口将保持打开")
        print("提示: 按 Ctrl+C 可以停止服务")
        print("提示: 关闭此窗口将停止服务\n")
        
        # 使用 uvicorn.run 启动服务（会阻塞直到服务停止）
        if getattr(sys, 'frozen', False):
            # 打包后的环境：需要先导入 app 对象
            try:
                from src.api_server import app
            except ImportError as e:
                # 如果相对导入失败，尝试绝对导入
                import importlib.util
                base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else project_root
                api_server_path = base_path / "src" / "api_server.py"
                
                if api_server_path.exists():
                    spec = importlib.util.spec_from_file_location("api_server", api_server_path)
                    api_server = importlib.util.module_from_spec(spec)
                    sys.modules["api_server"] = api_server
                    spec.loader.exec_module(api_server)
                    app = api_server.app
                else:
                    raise ImportError(f"Cannot find api_server.py: {api_server_path}") from e
            
            # 打包后的 exe 不支持 reload 模式，强制禁用
            args.reload = False
            if args.workers > 1:
                args.workers = 1
            
            # 打包后：直接使用 app 对象
            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
                reload=False,  # 打包后不支持 reload
                workers=args.workers,
                log_level="info",
                access_log=True
            )
        else:
            # 开发模式：使用字符串路径（支持 reload，这是原来的方式）
            uvicorn.run(
                "src.api_server:app",  # 字符串路径，支持 reload
                host=args.host,
                port=args.port,
                reload=args.reload,
                workers=args.workers if not args.reload else 1,
                log_level="info",
                access_log=True
            )
    except KeyboardInterrupt:
        print("\n\n收到停止信号，正在关闭服务...")
        print("服务已停止")
        # 等待一下让用户看到消息
        import time
        time.sleep(1)
    except Exception as e:
        print(f"\n\n启动服务失败: {e}")
        import traceback
        traceback.print_exc()
        print("\n按任意键退出...")
        try:
            input()
        except:
            import time
            time.sleep(5)  # 等待5秒让用户看到错误信息
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # 用户按 Ctrl+C，正常退出
        print("\n\n服务已停止")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n严重错误: {e}")
        import traceback
        traceback.print_exc()
        print("\n按任意键退出...")
        try:
            input()
        except:
            import time
            time.sleep(5)  # 等待5秒让用户看到错误信息
        sys.exit(1)

