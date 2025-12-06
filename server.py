"""
PSD 智能对象替换 API 服务启动入口
项目根目录启动脚本
"""

import sys
import uvicorn
from pathlib import Path

# 添加项目路径
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
    print(f"自动重载: {'✅ 启用' if args.reload else '❌ 禁用'}")
    print(f"工作进程: {args.workers}")
    print("=" * 70)
    print("\n⚠️  注意事项:")
    print("   - 确保 Photoshop 已安装并可访问")
    print("   - 由于 Photoshop 限制，建议使用单进程模式（workers=1）")
    print("   - 建议以管理员权限运行，避免权限问题")
    print("=" * 70)
    print()
    
    # 警告：多个工作进程可能导致 Photoshop 连接问题
    if args.workers > 1:
        print("⚠️  警告: 多个工作进程可能导致 Photoshop 连接问题")
        print("   建议使用 workers=1（单进程模式）")
        print()
        # 强制使用单进程
        args.workers = 1
    
    # 启动服务
    try:
        uvicorn.run(
            "src.api_server:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n服务已停止")
    except Exception as e:
        print(f"\n\n❌ 启动服务失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

