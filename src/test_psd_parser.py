"""
测试 PSD 解析功能
使用 examples/shirt.psd 文件进行测试
"""
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 直接导入 psd_parser 模块文件，避免触发 __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location("psd_parser", project_root / "src" / "psd_parser.py")
psd_parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psd_parser)

export_psd_to_json = psd_parser.export_psd_to_json
parse_psd_to_dict = psd_parser.parse_psd_to_dict


def test_psd_parser():
    """测试 PSD 解析功能"""
    # 使用全局的 project_root
    psd_path = project_root / "examples" / "shirt.psd"
    output_path = project_root / "examples" / "shirt_info.json"
    
    print("=" * 60)
    print("PSD 解析测试")
    print("=" * 60)
    print(f"PSD 文件路径: {psd_path}")
    print(f"输出 JSON 路径: {output_path}")
    print()
    
    # 检查文件是否存在
    if not psd_path.exists():
        print(f"❌ 错误: PSD 文件不存在: {psd_path}")
        return
    
    try:
        # 方法1: 直接导出 JSON
        print("📝 方法1: 导出 JSON 文件...")
        export_psd_to_json(psd_path, output_path, indent=2)
        print()
        
        # 方法2: 获取字典数据并进行分析
        print("📊 方法2: 解析并分析数据...")
        psd_data = parse_psd_to_dict(psd_path)
        
        # 显示基本信息
        print("\n" + "=" * 60)
        print("PSD 文件基本信息")
        print("=" * 60)
        print(f"文件名: {psd_data['file_name']}")
        print(f"尺寸: {psd_data['width']} x {psd_data['height']} px")
        print(f"颜色模式: {psd_data['color_mode']}")
        if psd_data.get('depth'):
            print(f"位深度: {psd_data['depth']} bit")
        if psd_data.get('channels'):
            print(f"通道数: {psd_data['channels']}")
        if psd_data.get('resolution'):
            res = psd_data['resolution']
            if res.get('horizontal'):
                print(f"分辨率: {res['horizontal']} x {res.get('vertical', res['horizontal'])} dpi")
        
        # 显示统计信息
        print("\n" + "=" * 60)
        print("图层统计信息")
        print("=" * 60)
        stats = psd_data['statistics']
        print(f"图层总数: {stats['total']}")
        print(f"  - 像素图层: {stats['pixel']}")
        print(f"  - 图层组: {stats['group']}")
        print(f"  - 文本图层: {stats['text']}")
        print(f"  - 智能对象: {stats['smart_object']}")
        
        # 显示图层结构（前几层）
        print("\n" + "=" * 60)
        print("图层结构预览（前 10 层）")
        print("=" * 60)
        
        def print_layer_tree(layers, indent=0, max_depth=3, max_items=10, current_count=[0]):
            """递归打印图层树"""
            if current_count[0] >= max_items:
                return
            if indent > max_depth:
                return
                
            for layer in layers:
                if current_count[0] >= max_items:
                    print("  " * indent + "...")
                    return
                    
                prefix = "  " * indent
                layer_type_icon = {
                    "pixel": "🖼️",
                    "group": "📁",
                    "text": "📝",
                    "smart_object": "🔗"
                }.get(layer.get("layer_type", ""), "📄")
                
                visibility = "👁️" if layer.get("visible") else "🙈"
                name = layer.get("name", "未命名")
                layer_type = layer.get("layer_type", "unknown")
                
                print(f"{prefix}{layer_type_icon} {visibility} {name} ({layer_type})")
                current_count[0] += 1
                
                # 如果有子图层，递归打印
                if "children" in layer and layer["children"]:
                    print_layer_tree(layer["children"], indent + 1, max_depth, max_items, current_count)
        
        print_layer_tree(psd_data["layers"], max_items=10)
        
        # 查找智能对象
        print("\n" + "=" * 60)
        print("智能对象列表")
        print("=" * 60)
        
        def find_smart_objects(layers, path=""):
            """递归查找智能对象"""
            smart_objects = []
            for layer in layers:
                current_path = f"{path}/{layer['name']}" if path else layer['name']
                if layer.get("layer_type") == "smart_object":
                    smart_objects.append({
                        "name": layer["name"],
                        "path": current_path,
                        "visible": layer.get("visible", True),
                        "size": f"{layer.get('width', 0)}x{layer.get('height', 0)}"
                    })
                if "children" in layer:
                    smart_objects.extend(find_smart_objects(layer["children"], current_path))
            return smart_objects
        
        smart_objects = find_smart_objects(psd_data["layers"])
        if smart_objects:
            for i, so in enumerate(smart_objects, 1):
                visibility = "可见" if so["visible"] else "隐藏"
                print(f"{i}. {so['name']} ({so['path']}) - {visibility} - {so['size']}")
        else:
            print("未找到智能对象")
        
        # 验证 JSON 文件
        print("\n" + "=" * 60)
        print("验证导出的 JSON 文件")
        print("=" * 60)
        if output_path.exists():
            with open(output_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            file_size = output_path.stat().st_size
            print(f"✅ JSON 文件已生成")
            print(f"   文件大小: {file_size:,} 字节 ({file_size / 1024:.2f} KB)")
            print(f"   图层数量: {len(json_data.get('layers', []))}")
            print(f"   数据完整性: {'✅ 通过' if json_data.get('statistics') else '❌ 失败'}")
        else:
            print("❌ JSON 文件未生成")
        
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_psd_parser()
