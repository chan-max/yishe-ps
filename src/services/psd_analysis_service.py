"""
PSD 文件分析服务
专注于提取 PSD 文件的整体信息和智能对象详细信息
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from psd_tools import PSDImage
    from psd_tools.api.layers import Layer, SmartObjectLayer, Group
except ImportError:
    PSDImage = None
    SmartObjectLayer = None
    Group = None


def _print_layer_structure(layer_structure: List[Dict[str, Any]], indent: str = "", is_last: bool = True):
    """
    递归打印图层结构树
    
    Args:
        layer_structure: 图层结构列表
        indent: 当前缩进
        is_last: 是否是最后一个节点
    """
    for i, layer in enumerate(layer_structure):
        is_last_layer = i == len(layer_structure) - 1
        
        # 选择连接符
        connector = "└── " if is_last_layer else "├── "
        next_indent = indent + ("    " if is_last_layer else "│   ")
        
        # 获取图层类型标记
        layer_type = layer.get("type", "layer")
        type_markers = {
            "group": "[组]",
            "smart_object": "[智能对象]",
            "layer": "[图层]"
        }
        type_marker = type_markers.get(layer_type, f"[{layer_type}]")
        
        # 画板标记
        artboard_marker = " [画板]" if layer.get("is_artboard", False) else ""
        
        # 可见性标记
        visible_marker = "" if layer.get("visible", True) else " [隐藏]"
        
        # 打印图层信息
        layer_name = layer.get("name", "未知图层")
        print(f"{indent}{connector}{type_marker}{artboard_marker} {layer_name}{visible_marker}")
        
        # 如果有子图层，递归打印
        children = layer.get("children", [])
        if children:
            _print_layer_structure(children, next_indent, is_last_layer)


def analyze_psd(psd_path: str | Path) -> Dict[str, Any]:
    """
    分析 PSD 文件，提取整体信息和智能对象详细信息
    
    Args:
        psd_path: PSD 文件路径
    
    Returns:
        包含 PSD 分析结果的字典：
        - file_info: 文件基本信息
        - document_info: 文档信息（尺寸、分辨率等）
        - smart_objects: 智能对象列表（详细信息）
        - statistics: 统计信息
        - timestamp: 分析时间戳
    """
    if PSDImage is None:
        raise ImportError("psd-tools 库未安装，请运行: pip install psd-tools")
    
    psd_path = Path(psd_path)
    if not psd_path.exists():
        raise FileNotFoundError(f"PSD 文件不存在: {psd_path}")
    
    if psd_path.suffix.lower() != '.psd':
        raise ValueError(f"文件必须是 PSD 格式: {psd_path}")
    
    # 打开 PSD 文件
    psd = PSDImage.open(psd_path)
    
    # 提取文档基本信息
    document_info = {
        "width": int(psd.width),
        "height": int(psd.height),
        "color_mode": str(psd.color_mode),
        "depth": int(psd.depth) if psd.depth else None,
        "channels": int(psd.channels) if psd.channels else None,
    }
    
    # 提取分辨率信息
    if hasattr(psd, 'header') and psd.header:
        header = psd.header
        if hasattr(header, 'resolution') and header.resolution:
            resolution = header.resolution
            if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
                document_info["resolution"] = {
                    "horizontal": float(resolution[0]),
                    "vertical": float(resolution[1]),
                    "unit": "pixels/inch"  # PSD 通常使用像素/英寸
                }
            elif hasattr(resolution, 'x') and hasattr(resolution, 'y'):
                document_info["resolution"] = {
                    "horizontal": float(resolution.x),
                    "vertical": float(resolution.y),
                    "unit": "pixels/inch"
                }
    
    # 提取所有智能对象
    smart_objects = _extract_smart_objects(psd, parent_path="")

    # 图层结构（含层级，包含画板标记）
    layer_structure = _extract_layer_structure(psd, parent_path="")
    
    # 统计信息（增加画板数量统计）
    statistics = {
        "total_smart_objects": len(smart_objects),
        "total_layers": _count_all_layers(psd),
        "has_smart_objects": len(smart_objects) > 0,
        "artboard_count": _count_artboards(psd),
    }
    
    # 文件信息
    file_info = {
        "file_path": str(psd_path.absolute()),
        "file_name": psd_path.name,
        "file_size": psd_path.stat().st_size,
        "file_size_mb": round(psd_path.stat().st_size / 1024 / 1024, 2)
    }
    
    # 构建结果字典
    result = {
        "file_info": file_info,
        "document_info": document_info,
        "smart_objects": smart_objects,
        "statistics": statistics,
        "layer_structure": layer_structure,
        "timestamp": datetime.now().isoformat()
    }
    
    # 在控制台打印结构信息
    print("\n" + "=" * 80)
    print(f"📄 PSD 文件分析结果: {file_info['file_name']}")
    print("=" * 80)
    
    # 文件基本信息
    print(f"\n📋 文件信息:")
    print(f"   路径: {file_info['file_path']}")
    print(f"   大小: {file_info['file_size_mb']} MB ({file_info['file_size']} 字节)")
    
    # 文档信息
    print(f"\n📐 文档信息:")
    print(f"   尺寸: {document_info['width']} x {document_info['height']} 像素")
    if 'resolution' in document_info:
        res = document_info['resolution']
        print(f"   分辨率: {res['horizontal']} x {res['vertical']} {res.get('unit', 'pixels/inch')}")
    print(f"   颜色模式: {document_info['color_mode']}")
    if document_info.get('depth'):
        print(f"   深度: {document_info['depth']} 位")
    if document_info.get('channels'):
        print(f"   通道数: {document_info['channels']}")
    
    # 统计信息
    print(f"\n📊 统计信息:")
    print(f"   图层总数: {statistics['total_layers']}")
    print(f"   智能对象数量: {statistics['total_smart_objects']}")
    print(f"   画板数量: {statistics['artboard_count']}")
    
    # 智能对象列表
    if smart_objects:
        print(f"\n🎯 智能对象列表:")
        for i, so in enumerate(smart_objects, 1):
            print(f"   {i}. {so['name']} (路径: {so['path']})")
            size = so.get('size', {})
            if size:
                print(f"      尺寸: {size.get('width', 0)} x {size.get('height', 0)} 像素")
            pos = so.get('position', {})
            if pos:
                print(f"      位置: ({pos.get('x', 0)}, {pos.get('y', 0)})")
            print(f"      可见: {'是' if so.get('visible', True) else '否'}")
    
    # 图层结构树
    if layer_structure:
        print(f"\n🌳 图层结构:")
        _print_layer_structure(layer_structure)
    
    print("\n" + "=" * 80 + "\n")
    
    return result


def _extract_smart_objects(psd: PSDImage, parent_path: str = "") -> List[Dict[str, Any]]:
    """
    递归提取所有智能对象图层
    
    Args:
        psd: PSD 图像对象或图层组
        parent_path: 父图层路径
    
    Returns:
        智能对象信息列表
    """
    smart_objects = []
    
    def traverse_layers(layers, current_path: str = ""):
        """递归遍历图层"""
        for layer in layers:
            try:
                layer_name = layer.name if hasattr(layer, 'name') else "未知图层"
                layer_path = f"{current_path}/{layer_name}" if current_path else layer_name
                
                # 检查是否是智能对象
                if isinstance(layer, SmartObjectLayer):
                    so_info = _extract_smart_object_details(layer, layer_path)
                    smart_objects.append(so_info)
                
                # 如果是图层组，递归处理子图层
                if isinstance(layer, Group) or (hasattr(layer, 'is_group') and layer.is_group()):
                    if hasattr(layer, '__iter__'):
                        traverse_layers(layer, layer_path)
                        
            except Exception as e:
                # 跳过无法处理的图层
                continue
    
    # 从顶层图层开始遍历
    # PSDImage 对象本身是可迭代的，包含所有顶层图层
    try:
        if hasattr(psd, '__iter__'):
            traverse_layers(psd, parent_path)
    except Exception as e:
        # 如果遍历失败，尝试其他方法
        if hasattr(psd, 'layers'):
            traverse_layers(psd.layers, parent_path)
    
    return smart_objects


def _extract_smart_object_details(layer: SmartObjectLayer, layer_path: str) -> Dict[str, Any]:
    """
    提取智能对象的详细信息
    
    Args:
        layer: 智能对象图层
        layer_path: 图层路径
    
    Returns:
        智能对象详细信息字典
    """
    info: Dict[str, Any] = {
        "name": layer.name if hasattr(layer, 'name') else "未知",
        "path": layer_path,
        "visible": layer.visible if hasattr(layer, 'visible') else True,
        "opacity": float(layer.opacity) / 255.0 if hasattr(layer, 'opacity') and layer.opacity is not None else 1.0,
        "blend_mode": str(layer.blend_mode) if hasattr(layer, 'blend_mode') and layer.blend_mode else "normal",
    }
    
    # 位置信息
    if hasattr(layer, 'left') and layer.left is not None:
        info["position"] = {
            "x": int(layer.left),
            "y": int(layer.top) if hasattr(layer, 'top') and layer.top is not None else 0,
            "left": int(layer.left),
            "top": int(layer.top) if hasattr(layer, 'top') and layer.top is not None else 0,
            "right": int(layer.right) if hasattr(layer, 'right') and layer.right is not None else 0,
            "bottom": int(layer.bottom) if hasattr(layer, 'bottom') and layer.bottom is not None else 0,
        }
    else:
        info["position"] = {
            "x": 0,
            "y": 0,
            "left": 0,
            "top": 0,
            "right": 0,
            "bottom": 0,
        }
    
    # 尺寸信息
    width = 0
    height = 0
    
    if hasattr(layer, 'width') and layer.width is not None:
        width = int(layer.width)
    elif hasattr(layer, 'right') and hasattr(layer, 'left') and layer.right is not None and layer.left is not None:
        width = int(layer.right - layer.left)
    
    if hasattr(layer, 'height') and layer.height is not None:
        height = int(layer.height)
    elif hasattr(layer, 'bottom') and hasattr(layer, 'top') and layer.bottom is not None and layer.top is not None:
        height = int(layer.bottom - layer.top)
    
    info["size"] = {
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 4) if height > 0 else 0
    }
    
    # 边界框（bounds）
    if hasattr(layer, 'bbox'):
        bbox = layer.bbox
        if bbox:
            info["bounds"] = {
                "x1": int(bbox.x1) if hasattr(bbox, 'x1') else 0,
                "y1": int(bbox.y1) if hasattr(bbox, 'y1') else 0,
                "x2": int(bbox.x2) if hasattr(bbox, 'x2') else 0,
                "y2": int(bbox.y2) if hasattr(bbox, 'y2') else 0,
            }
    
    # 智能对象特定信息
    if hasattr(layer, 'smart_object') and layer.smart_object:
        so = layer.smart_object
        info["smart_object"] = {}
        
        if hasattr(so, 'unique_id'):
            info["smart_object"]["unique_id"] = str(so.unique_id)
        
        if hasattr(so, 'file_type'):
            info["smart_object"]["file_type"] = str(so.file_type)
        
        if hasattr(so, 'kind'):
            info["smart_object"]["kind"] = str(so.kind)
        
        # 尝试获取嵌入的文档信息
        if hasattr(so, 'embedded_document'):
            embedded = so.embedded_document
            if embedded:
                info["smart_object"]["embedded_document"] = {
                    "width": int(embedded.width) if hasattr(embedded, 'width') else None,
                    "height": int(embedded.height) if hasattr(embedded, 'height') else None,
                }
    
    # 变换信息（如果有）
    if hasattr(layer, 'transform'):
        transform = layer.transform
        if transform:
            info["transform"] = {
                "xx": float(transform.xx) if hasattr(transform, 'xx') else None,
                "xy": float(transform.xy) if hasattr(transform, 'xy') else None,
                "yx": float(transform.yx) if hasattr(transform, 'yx') else None,
                "yy": float(transform.yy) if hasattr(transform, 'yy') else None,
                "tx": float(transform.tx) if hasattr(transform, 'tx') else None,
                "ty": float(transform.ty) if hasattr(transform, 'ty') else None,
            }
    
    # 图层效果（如果有）
    if hasattr(layer, 'effects') and layer.effects:
        effects_list = []
        if isinstance(layer.effects, (list, tuple)):
            for effect in layer.effects:
                if hasattr(effect, 'kind'):
                    effects_list.append(str(effect.kind))
        info["has_effects"] = True
        info["effects"] = effects_list
    else:
        info["has_effects"] = False
    
    # 图层蒙版（如果有）
    if hasattr(layer, 'has_mask') and layer.has_mask():
        info["has_mask"] = True
        if hasattr(layer, 'mask') and layer.mask:
            mask = layer.mask
            info["mask"] = {
                "left": int(mask.left) if hasattr(mask, 'left') and mask.left is not None else 0,
                "top": int(mask.top) if hasattr(mask, 'top') and mask.top is not None else 0,
                "right": int(mask.right) if hasattr(mask, 'right') and mask.right is not None else 0,
                "bottom": int(mask.bottom) if hasattr(mask, 'bottom') and mask.bottom is not None else 0,
            }
    else:
        info["has_mask"] = False
    
    return info


def _extract_layer_structure(psd: PSDImage, parent_path: str = "", depth: int = 0) -> List[Dict[str, Any]]:
    """提取完整图层树结构。"""
    layers_info: List[Dict[str, Any]] = []

    def map_layer(layer, current_path: str, current_depth: int) -> Dict[str, Any]:
        name = layer.name if hasattr(layer, "name") else "未知图层"
        # 基础类型：普通图层 / 组 / 智能对象
        is_group = isinstance(layer, Group) or (hasattr(layer, "is_group") and layer.is_group())
        layer_type = (
            "smart_object"
            if isinstance(layer, SmartObjectLayer)
            else "group"
            if is_group
            else "layer"
        )

        # 仅根据 psd-tools 的真实画板标记判断（不再把顶层 group 视为画板）
        is_artboard = _is_artboard_layer(layer)

        info: Dict[str, Any] = {
            "name": name,
            "path": current_path,
            "type": layer_type,
            "visible": layer.visible if hasattr(layer, "visible") else True,
            "opacity": float(layer.opacity) / 255.0 if hasattr(layer, "opacity") and layer.opacity is not None else 1.0,
            "blend_mode": str(layer.blend_mode) if hasattr(layer, "blend_mode") and layer.blend_mode else "normal",
            "depth": current_depth,
            "children": [],
            "is_artboard": is_artboard,
        }

        is_group = isinstance(layer, Group) or (hasattr(layer, "is_group") and layer.is_group())
        if is_group and hasattr(layer, "__iter__"):
            for child in layer:
                child_path = f"{current_path}/{child.name}" if current_path else (child.name if hasattr(child, "name") else "未知图层")
                info["children"].append(map_layer(child, child_path, current_depth + 1))

        return info

    try:
        if hasattr(psd, "__iter__"):
            for layer in psd:
                layer_path = f"{parent_path}/{layer.name}" if parent_path else (layer.name if hasattr(layer, "name") else "未知图层")
                layers_info.append(map_layer(layer, layer_path, depth))
        elif hasattr(psd, "layers"):
            for layer in psd.layers:
                layer_path = f"{parent_path}/{layer.name}" if parent_path else (layer.name if hasattr(layer, "name") else "未知图层")
                layers_info.append(map_layer(layer, layer_path, depth))
    except Exception:
        pass

    return layers_info


def _count_all_layers(psd: PSDImage) -> int:
    """
    统计所有图层数量（包括嵌套图层）
    
    Args:
        psd: PSD 图像对象
    
    Returns:
        图层总数
    """
    count = 0
    
    def count_recursive(layers):
        nonlocal count
        for layer in layers:
            count += 1
            if isinstance(layer, Group) or (hasattr(layer, 'is_group') and layer.is_group()):
                if hasattr(layer, '__iter__'):
                    count_recursive(layer)
    
    try:
        if hasattr(psd, '__iter__'):
            count_recursive(psd)
        elif hasattr(psd, 'layers'):
            count_recursive(psd.layers)
    except Exception:
        pass
    
    return count


def _count_artboards(psd: PSDImage) -> int:
    """
    统计画板数量。
    
    规则：
    1. 如果是带有 artboard / is_artboard 标记的 Group，则视为真实的 Photoshop 画板；
    2. 此外，顶层的 Group（depth == 0）也视为一个“逻辑画板”，方便业务把每个大组当作一个版位。
    """
    artboard_count = 0

    def traverse(layers, depth: int):
        nonlocal artboard_count
        for layer in layers:
            try:
                is_group = isinstance(layer, Group) or (hasattr(layer, "is_group") and layer.is_group())

                is_real_artboard = False
                try:
                    if hasattr(layer, "artboard") and layer.artboard:
                        is_real_artboard = True
                    elif hasattr(layer, "is_artboard") and getattr(layer, "is_artboard"):
                        is_real_artboard = True
                except Exception:
                    is_real_artboard = False

                # 真·画板 或 顶层组 -> 计为一个画板
                if is_real_artboard or (is_group and depth == 0):
                    artboard_count += 1

                if is_group and hasattr(layer, "__iter__"):
                    traverse(layer, depth + 1)
            except Exception:
                continue

    try:
        if hasattr(psd, "__iter__"):
            traverse(psd, 0)
        elif hasattr(psd, "layers"):
            traverse(psd.layers, 0)
    except Exception:
        pass

    return artboard_count

