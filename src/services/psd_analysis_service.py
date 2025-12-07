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
    
    # 统计信息
    statistics = {
        "total_smart_objects": len(smart_objects),
        "total_layers": _count_all_layers(psd),
        "has_smart_objects": len(smart_objects) > 0
    }
    
    # 文件信息
    file_info = {
        "file_path": str(psd_path.absolute()),
        "file_name": psd_path.name,
        "file_size": psd_path.stat().st_size,
        "file_size_mb": round(psd_path.stat().st_size / 1024 / 1024, 2)
    }
    
    return {
        "file_info": file_info,
        "document_info": document_info,
        "smart_objects": smart_objects,
        "statistics": statistics,
        "timestamp": datetime.now().isoformat()
    }


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

