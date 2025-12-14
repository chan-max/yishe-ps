"""
使用 psd-tools 解析 PSD 文件并导出为 JSON
"""
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from psd_tools import PSDImage
from psd_tools.api.layers import Layer, PixelLayer, Group, TypeLayer, SmartObjectLayer
from psd_tools.constants import BlendMode

# 设置标准输出和错误输出为 UTF-8 编码，避免 Windows GBK 编码问题
if sys.platform == 'win32':
    # 重新配置标准输出和错误输出为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'


def extract_layer_info(layer: Layer, parent_path: str = "") -> Dict[str, Any]:
    """
    递归提取图层信息
    
    Args:
        layer: PSD 图层对象
        parent_path: 父图层路径，用于构建完整路径
        
    Returns:
        包含图层信息的字典
    """
    layer_path = f"{parent_path}/{layer.name}" if parent_path else layer.name
    
    # 基础信息
    layer_info: Dict[str, Any] = {
        "name": layer.name,
        "path": layer_path,
        "visible": layer.visible,
        "opacity": float(layer.opacity) / 255.0 if layer.opacity is not None else 1.0,
        "blend_mode": str(layer.blend_mode) if layer.blend_mode else "normal",
        "left": int(layer.left) if layer.left is not None else 0,
        "top": int(layer.top) if layer.top is not None else 0,
        "right": int(layer.right) if layer.right is not None else 0,
        "bottom": int(layer.bottom) if layer.bottom is not None else 0,
        "width": int(layer.width) if layer.width is not None else 0,
        "height": int(layer.height) if layer.height is not None else 0,
        "type": type(layer).__name__,
    }
    
    # 根据图层类型添加特定信息
    if isinstance(layer, PixelLayer):
        layer_info["layer_type"] = "pixel"
        layer_info["has_mask"] = layer.has_mask()
        if layer.has_mask():
            mask = layer.mask
            if mask:
                layer_info["mask"] = {
                    "left": int(mask.left) if mask.left is not None else 0,
                    "top": int(mask.top) if mask.top is not None else 0,
                    "right": int(mask.right) if mask.right is not None else 0,
                    "bottom": int(mask.bottom) if mask.bottom is not None else 0,
                }
    
    elif isinstance(layer, Group) or layer.is_group():
        layer_info["layer_type"] = "group"
        layer_info["is_group"] = True
        layer_info["clipped"] = layer.clipped if hasattr(layer, 'clipped') else False
        # 递归处理子图层
        layer_info["children"] = []
        for child in layer:
            child_info = extract_layer_info(child, layer_path)
            layer_info["children"].append(child_info)
    
    elif isinstance(layer, TypeLayer):
        layer_info["layer_type"] = "text"
        layer_info["text"] = layer.text if hasattr(layer, 'text') else ""
        engine_data = layer.engine_data if hasattr(layer, 'engine_data') else None
        if engine_data:
            layer_info["engine_data"] = str(engine_data)  # 转换为字符串，因为可能包含复杂对象
    
    elif isinstance(layer, SmartObjectLayer):
        layer_info["layer_type"] = "smart_object"
        layer_info["is_smart_object"] = True
        # 智能对象可能包含嵌入的文档
        if hasattr(layer, 'smart_object') and layer.smart_object:
            so = layer.smart_object
            layer_info["smart_object"] = {
                "unique_id": str(so.unique_id) if hasattr(so, 'unique_id') else None,
                "file_type": str(so.file_type) if hasattr(so, 'file_type') else None,
            }
    
    # 提取其他可能的属性
    if hasattr(layer, 'effects') and layer.effects:
        layer_info["has_effects"] = True
        # 效果信息可能很复杂，这里只标记
        layer_info["effects_count"] = len(layer.effects) if isinstance(layer.effects, (list, tuple)) else 1
    
    # 提取标签信息（如果有）
    if hasattr(layer, 'tagged_blocks'):
        layer_info["has_tagged_blocks"] = True
    
    return layer_info


def parse_psd_to_dict(psd_path: Path) -> Dict[str, Any]:
    """
    解析 PSD 文件并转换为字典
    
    Args:
        psd_path: PSD 文件路径
        
    Returns:
        包含 PSD 所有信息的字典
    """
    psd = PSDImage.open(psd_path)
    
    # 文档基本信息
    result: Dict[str, Any] = {
        "file_path": str(psd_path),
        "file_name": psd_path.name,
        "width": int(psd.width),
        "height": int(psd.height),
        "color_mode": str(psd.color_mode),
        "depth": int(psd.depth) if psd.depth else None,
        "channels": int(psd.channels) if psd.channels else None,
    }
    
    # 颜色模式信息
    if hasattr(psd, 'color_mode_data'):
        result["color_mode_data"] = str(psd.color_mode_data)
    
    # 分辨率信息
    if hasattr(psd, 'header'):
        header = psd.header
        result["resolution"] = {
            "horizontal": float(header.resolution[0]) if hasattr(header, 'resolution') and header.resolution else None,
            "vertical": float(header.resolution[1]) if hasattr(header, 'resolution') and header.resolution and len(header.resolution) > 1 else None,
        }
    
    # 提取所有图层
    result["layers"] = []
    for layer in psd:
        layer_info = extract_layer_info(layer)
        result["layers"].append(layer_info)
    
    # 统计信息
    def count_layers(layers: List[Dict[str, Any]]) -> Dict[str, int]:
        """递归统计图层数量和类型"""
        stats = {
            "total": 0,
            "pixel": 0,
            "group": 0,
            "text": 0,
            "smart_object": 0,
        }
        for layer in layers:
            stats["total"] += 1
            layer_type = layer.get("layer_type", "unknown")
            if layer_type in stats:
                stats[layer_type] += 1
            if "children" in layer:
                child_stats = count_layers(layer["children"])
                for key in stats:
                    stats[key] += child_stats[key]
        return stats
    
    result["statistics"] = count_layers(result["layers"])
    
    return result


def export_psd_to_json(psd_path: Path, output_path: Optional[Path] = None, indent: int = 2) -> Path:
    """
    解析 PSD 文件并导出为 JSON
    
    Args:
        psd_path: PSD 文件路径
        output_path: 输出 JSON 文件路径，如果为 None 则自动生成
        indent: JSON 缩进空格数
        
    Returns:
        输出的 JSON 文件路径
    """
    psd_path = Path(psd_path)
    if not psd_path.exists():
        raise FileNotFoundError(f"PSD 文件不存在: {psd_path}")
    
    # 解析 PSD
    print(f"正在解析 PSD 文件: {psd_path}")
    psd_data = parse_psd_to_dict(psd_path)
    
    # 确定输出路径
    if output_path is None:
        output_path = psd_path.parent / f"{psd_path.stem}_info.json"
    else:
        output_path = Path(output_path)
    
    # 导出 JSON
    print(f"正在导出 JSON 到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(psd_data, f, ensure_ascii=False, indent=indent)
    
    print(f"✅ 导出完成！")
    print(f"   - 文档尺寸: {psd_data['width']}x{psd_data['height']}")
    print(f"   - 图层总数: {psd_data['statistics']['total']}")
    print(f"   - 像素图层: {psd_data['statistics']['pixel']}")
    print(f"   - 图层组: {psd_data['statistics']['group']}")
    print(f"   - 文本图层: {psd_data['statistics']['text']}")
    print(f"   - 智能对象: {psd_data['statistics']['smart_object']}")
    
    return output_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="解析 PSD 文件并导出为 JSON")
    parser.add_argument("--psd", type=str, required=True, help="PSD 文件路径")
    parser.add_argument("--output", type=str, default=None, help="输出 JSON 文件路径（可选，默认与 PSD 同目录）")
    parser.add_argument("--indent", type=int, default=2, help="JSON 缩进空格数（默认 2）")
    
    args = parser.parse_args()
    
    try:
        export_psd_to_json(Path(args.psd), Path(args.output) if args.output else None, args.indent)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

