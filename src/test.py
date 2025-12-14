"""
测试脚本：调用 PSD 智能对象替换功能

快速开始：
1. 修改 test_basic_usage() 函数中的路径：
   - psd_path: 你的 PSD 套图文件路径
   - image_path: 要替换的素材图片路径
   
2. 修改 config 配置（可选）：
   - export_dir: 导出目录（必需）
   - output_filename: 导出文件名（可选）
   - smart_object_name: 智能对象名称（可选，不指定则替换第一个找到的）
   - tile_size: 图片缩放分块尺寸（可选，默认512）

3. 运行脚本：
   python src/test.py

示例代码：
    from src.test import process_psd_with_image
"""
import sys
import os

# 设置标准输出和错误输出为 UTF-8 编码，避免 Windows GBK 编码问题
if sys.platform == 'win32':
    # 重新配置标准输出和错误输出为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    config = {
        'export_dir': 'D:/output',
        'smart_object_name': '图片',
        'output_filename': 'result.png'
    }
    
    result = process_psd_with_image(
        psd_path='D:/templates/template.psd',
        image_path='D:/images/image.jpg',
        config=config
    )
    print(f"导出成功: {result}")
"""

import sys
import importlib.util
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入封装函数（由于文件名包含连字符，使用 importlib）
module_path = Path(__file__).parent / "psd-img-replace-smartobject.py"
spec = importlib.util.spec_from_file_location("psd_replace", module_path)
psd_replace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psd_replace)

process_psd_with_image = psd_replace.process_psd_with_image


def test_basic_usage():
    """基础使用示例 - 不指定智能对象名称（自动替换第一个找到的）"""
    print("=" * 60)
    print("测试 1: 基础使用（不指定智能对象名称）")
    print("=" * 60)
    print("说明: 如果不指定 smart_object_name，脚本会自动找到所有智能对象")
    print("      并替换第一个找到的智能对象")
    print("=" * 60)
    
    # ========== 在这里修改你的路径 ==========
    psd_path = r"D:\freepik\mouse-pad-mockup\534dd19e-7675-4eea-9c26-4a9a0ca701d5.psd"  # 套图路径（PSD文件）
    image_path = r"D:\workspace\yishe-ps\examples\re.jpg"      # 素材图路径（要替换的图片）
    # ========================================
    
    # 配置参数 - 不指定 smart_object_name，会自动替换第一个找到的智能对象
    config = {
        'export_dir': r"D:\workspace\yishe-ps\output",        # 导出目录
        'output_filename': 'result_basic.png',                 # 导出文件名（可选）
        'tile_size': 512,                                      # 缩放分块尺寸（可选，默认512）
        # 'smart_object_name': None,                          # 不指定 = 自动替换第一个找到的智能对象
        # 'verbose': True,                                     # 可选：是否显示详细信息（默认True）
    }
    
    try:
        result = process_psd_with_image(
            psd_path=psd_path,
            image_path=image_path,
            config=config
        )
        print(f"\n✅ 成功！导出文件: {result}")
        print("\n提示: 如果PSD中有多个智能对象，脚本会显示所有找到的智能对象列表")
        print("      然后自动替换第一个。如果需要替换特定的智能对象，")
        print("      请在 config 中添加 'smart_object_name': '图层名称'")
        return result
    except Exception as e:
        print(f"\n❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_with_smart_object_name():
    """指定智能对象名称的示例（当PSD中有多个智能对象时使用）"""
    print("\n" + "=" * 60)
    print("测试 2: 指定智能对象名称")
    print("=" * 60)
    print("说明: 当PSD中有多个智能对象时，可以通过名称指定要替换哪一个")
    print("=" * 60)
    
    psd_path = r"D:\workspace\yishe-ps\examples\template.psd"
    image_path = r"D:\workspace\yishe-ps\examples\sq.jpg"
    
    config = {
        'export_dir': r"D:\workspace\yishe-ps\output",
        'smart_object_name': '图片',  # 指定要替换的智能对象名称（需要先运行一次查看有哪些智能对象）
        'output_filename': 'result_named.png',
        'tile_size': 512
    }
    
    try:
        result = process_psd_with_image(
            psd_path=psd_path,
            image_path=image_path,
            config=config
        )
        print(f"\n✅ 成功！导出文件: {result}")
        print("\n提示: 如果不确定智能对象的名称，可以先不指定 smart_object_name")
        print("      运行一次，脚本会显示所有找到的智能对象列表")
        return result
    except Exception as e:
        print(f"\n❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_quiet_mode():
    """静默模式示例（不显示详细信息）"""
    print("\n" + "=" * 60)
    print("测试 3: 静默模式")
    print("=" * 60)
    
    psd_path = r"D:\workspace\yishe-ps\examples\template.psd"
    image_path = r"D:\workspace\yishe-ps\examples\re.jpg"
    
    config = {
        'export_dir': r"D:\workspace\yishe-ps\output",
        'output_filename': 'result_quiet.png',
        'verbose': False  # 静默模式，不显示详细信息
    }
    
    try:
        result = process_psd_with_image(
            psd_path=psd_path,
            image_path=image_path,
            config=config
        )
        print(f"\n✅ 成功！导出文件: {result}")
        return result
    except Exception as e:
        print(f"\n❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_batch_processing():
    """批量处理示例"""
    print("\n" + "=" * 60)
    print("测试 4: 批量处理")
    print("=" * 60)
    
    # 定义多个素材图
    images = [
        r"D:\workspace\yishe-ps\examples\re.jpg",
        r"D:\workspace\yishe-ps\examples\sq.jpg",
    ]
    
    psd_path = r"D:\workspace\yishe-ps\examples\template.psd"
    
    results = []
    for i, image_path in enumerate(images, 1):
        print(f"\n处理第 {i} 张图片: {Path(image_path).name}")
        
        config = {
            'export_dir': r"D:\workspace\yishe-ps\output",
            'output_filename': f'batch_result_{i}.png',
            'verbose': True
        }
        
        try:
            result = process_psd_with_image(
                psd_path=psd_path,
                image_path=image_path,
                config=config
            )
            results.append(result)
            print(f"✅ 第 {i} 张处理完成: {result}")
        except Exception as e:
            print(f"❌ 第 {i} 张处理失败: {e}")
            results.append(None)
    
    print(f"\n批量处理完成！成功: {sum(1 for r in results if r is not None)}/{len(results)}")
    return results


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("PSD 智能对象替换测试")
    print("=" * 60)
    print("\n使用说明:")
    print("1. 修改 test_basic_usage() 函数中的 psd_path 和 image_path")
    print("2. 根据需要修改 config 配置参数")
    print("3. 运行脚本: python src/test.py")
    print("=" * 60)
    
    # 检查文件是否存在
    test_psd_path = Path(r"D:\freepik\mouse-pad-mockup\534dd19e-7675-4eea-9c26-4a9a0ca701d5.psd")
    test_image_path = Path(r"D:\workspace\yishe-ps\examples\re.jpg")
    
    if not test_psd_path.exists():
        print(f"\n⚠️  警告: PSD 文件不存在: {test_psd_path}")
        print("请检查路径是否正确")
        return
    
    if not test_image_path.exists():
        print(f"\n⚠️  警告: 素材图文件不存在: {test_image_path}")
        print("请检查路径是否正确")
        return
    
    print(f"\n✅ 文件检查通过:")
    print(f"   PSD文件: {test_psd_path}")
    print(f"   素材图: {test_image_path}")
    
    # 运行测试（根据需要取消注释）
    
    # 测试 1: 基础使用（推荐从这里开始）
    test_basic_usage()
    
    # 测试 2: 指定智能对象名称
    # test_with_smart_object_name()
    
    # 测试 3: 静默模式
    # test_quiet_mode()
    
    # 测试 4: 批量处理
    # test_batch_processing()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

