"""简单的 Photoshop 连接和打开 PSD 示例。"""

import sys
from pathlib import Path
from photoshop import Session

from .utils import ensure_photoshop_running


def open_psd_example(psd_path: str | Path, auto_start: bool = True):
    """连接本地 Photoshop 并打开 PSD 文件的简单示例。
    
    Args:
        psd_path: PSD 文件路径
        auto_start: 如果 Photoshop 未运行是否自动启动，默认 True
    """
    psd_path = Path(psd_path)
    
    # 检查文件是否存在
    if not psd_path.exists():
        raise FileNotFoundError(f"PSD 文件不存在: {psd_path}")
    
    # 确保 Photoshop 正在运行
    if not ensure_photoshop_running(auto_start=auto_start):
        raise RuntimeError("无法连接到 Photoshop，请确保 Photoshop 已安装并可以启动")
    
    print(f"正在连接 Photoshop...")
    
    # 创建 Photoshop 会话（会自动连接本地运行的 Photoshop）
    with Session() as ps:
        app = ps.app
        print(f"✅ 成功连接到 Photoshop！版本: {app.version}")
        
        # 打开 PSD 文件
        print(f"正在打开 PSD 文件: {psd_path}")
        doc = app.open(str(psd_path))
        
        print(f"✅ 成功打开文档: {doc.name}")
        print(f"   文档尺寸: {doc.width} x {doc.height} 像素")
        print(f"   分辨率: {doc.resolution} DPI")
        print(f"   颜色模式: {doc.mode}")
        print(f"   图层数量: {len(doc.layers)}")
        
        # 列出前几个图层名称
        if doc.layers:
            print(f"\n前 5 个图层:")
            for i, layer in enumerate(doc.layers[:5], 1):
                print(f"   {i}. {layer.name}")
        
        # 保持文档打开（会话结束后会自动关闭）
        print(f"\n文档将在会话结束后自动关闭")
        
        return doc


if __name__ == "__main__":
    # 方式1：直接在代码中指定路径（取消下面的注释并修改路径）
    # psd_file = r"D:\模板\example.psd"
    # open_psd_example(psd_file, auto_start=True)  # auto_start=True 会自动启动 PS
    
    # 方式2：运行时输入路径
    psd_file = input("请输入 PSD 文件路径: ").strip().strip('"')
    
    # 如果没有输入，提示用户
    if not psd_file:
        print("未输入路径，请在代码中设置 psd_file 变量")
        print("示例: psd_file = r'D:\\模板\\example.psd'")
        sys.exit(1)
    
    # 询问是否自动启动 Photoshop
    auto_start_input = input("如果 Photoshop 未运行，是否自动启动？(Y/n): ").strip().lower()
    auto_start = auto_start_input != 'n'
    
    try:
        open_psd_example(psd_file, auto_start=auto_start)
        print("\n✅ 示例执行完成！")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

