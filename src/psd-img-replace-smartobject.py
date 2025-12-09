"""
PSD 智能对象替换脚本
功能：找到 PSD 中的智能对象图层，替换为新图片，并导出到指定目录
"""

import gc
import sys
import os
import stat
from pathlib import Path
from typing import Optional, List

from photoshop import Session
from photoshop.api import ActionDescriptor, ActionReference
from photoshop.api.enumerations import DialogModes, LayerKind

# 导入保存选项常量
# 根据 photoshop-python-api，使用数值常量
# 2 = SaveChanges.YES (保存更改)
# 1 = SaveChanges.NO (不保存)
# 0 = SaveChanges.PROMPT (提示保存)
class PsSaveOptions:
    """保存选项常量"""
    psSaveChanges = 2  # 保存更改
    psDoNotSaveChanges = 1  # 不保存
    psPromptToSaveChanges = 0  # 提示保存

# 支持相对导入和绝对导入
try:
    from .utils import ensure_photoshop_running, validate_job_inputs, resize_image_in_tiles
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.utils import ensure_photoshop_running, validate_job_inputs, resize_image_in_tiles


def check_write_permission(path: Path) -> tuple[bool, str]:
    """
    检查路径的写入权限
    
    Args:
        path: 要检查的路径（文件或目录）
    
    Returns:
        (是否有权限, 错误信息)
    """
    try:
        # 如果是文件，检查父目录
        check_path = path.parent if path.suffix else path
        
        # 检查目录是否存在，如果不存在尝试创建
        if not check_path.exists():
            try:
                check_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return False, f"没有权限创建目录: {check_path}"
        
        # 检查是否有写入权限
        if not os.access(check_path, os.W_OK):
            return False, f"没有写入权限: {check_path}"
        
        # 如果是文件且已存在，检查是否可以写入
        if path.exists() and path.is_file():
            if not os.access(path, os.W_OK):
                return False, f"文件已存在但没有写入权限: {path}"
        
        return True, ""
    except Exception as e:
        return False, f"检查权限时出错: {e}"


def check_photoshop_permissions() -> tuple[bool, str]:
    """
    检查 Photoshop 相关的权限
    
    Returns:
        (是否有权限, 错误信息)
    """
    try:
        # 检查临时目录权限（PS 可能需要）
        temp_dir = Path(os.environ.get('TEMP', os.environ.get('TMP', '.')))
        if not os.access(temp_dir, os.W_OK):
            return False, f"临时目录没有写入权限: {temp_dir}"
        return True, ""
    except Exception as e:
        return False, f"检查 Photoshop 权限时出错: {e}"


def debug_print_all_layers(doc, max_depth=10, current_depth=0, parent_path=""):
    """
    调试函数：打印所有图层信息，帮助排查问题
    
    Args:
        doc: Photoshop 文档对象
        max_depth: 最大递归深度
        current_depth: 当前深度
        parent_path: 父路径
    """
    if current_depth >= max_depth:
        return
    
    indent = "  " * current_depth
    
    def print_layer_info(layer, depth, path_prefix=""):
        """递归打印图层信息"""
        indent_str = "  " * depth
        try:
            layer_name = layer.name if hasattr(layer, 'name') else "未知名称"
            current_path = f"{path_prefix}/{layer_name}" if path_prefix else layer_name
            
            # 获取图层类型信息
            layer_info = []
            
            # 尝试获取 kind
            try:
                kind = layer.kind
                layer_info.append(f"kind={kind}")
                # 尝试获取枚举名称
                try:
                    kind_str = str(kind)
                    if 'SmartObject' in kind_str or 'smartObject' in kind_str or 'smart object' in kind_str.lower():
                        layer_info.append("🔗 可能是智能对象!")
                    kind_name = kind_str.split('.')[-1] if '.' in kind_str else kind_str
                    layer_info.append(f"kind_name={kind_name}")
                except:
                    pass
                
                # 检查是否等于 LayerKind.SmartObjectLayer
                try:
                    if kind == LayerKind.SmartObjectLayer:
                        layer_info.append("✅ 确认是智能对象(SmartObjectLayer)")
                    elif hasattr(LayerKind, 'SmartObjectLayer'):
                        so_kind = getattr(LayerKind, 'SmartObjectLayer')
                        if kind == so_kind:
                            layer_info.append("✅ 确认是智能对象(通过属性)")
                except:
                    pass
            except Exception as e:
                layer_info.append(f"kind=无法获取({type(e).__name__}: {e})")
            
            # 检查类名
            try:
                class_name = type(layer).__name__
                layer_info.append(f"类型={class_name}")
                if 'Smart' in class_name or 'smart' in class_name.lower():
                    layer_info.append("🔗 类名可能表示智能对象!")
            except:
                pass
            
            # 检查图层名称是否包含 "SmartObject" 关键字（不区分大小写）
            try:
                if layer_name and 'smartobject' in layer_name.lower():
                    layer_info.append(f"✅ 图层名称包含'SmartObject'关键字 - 将被识别为智能对象! (名称: {layer_name})")
            except:
                pass
            
            # 检查是否有 layers 属性（图层组）
            is_group = False
            try:
                sub_layers = layer.layers
                if sub_layers and len(sub_layers) > 0:
                    is_group = True
                    layer_info.append(f"图层组(有{len(sub_layers)}个子图层)")
            except:
                pass
            
            # 检查是否有 bounds
            try:
                bounds = layer.bounds
                if bounds:
                    layer_info.append(f"bounds={bounds[:4] if len(bounds) >= 4 else bounds}")
            except:
                pass
            
            print(f"{indent_str}[图层] {layer_name}")
            print(f"{indent_str}  路径: {current_path}")
            print(f"{indent_str}  信息: {', '.join(layer_info)}")
            
            # 递归处理子图层
            if is_group:
                print(f"{indent_str}  └─ 子图层:")
                try:
                    for sub_layer in layer.layers:
                        print_layer_info(sub_layer, depth + 1, current_path)
                except Exception as e:
                    print(f"{indent_str}    读取子图层失败: {e}")
                    
        except Exception as e:
            print(f"{indent_str}[图层] 读取失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    # 开始打印
    try:
        layers = doc.layers
        if not layers:
            print(f"{indent}[无图层]")
            return
        
        print(f"{indent}开始遍历 {len(layers)} 个顶层图层...")
        for i, layer in enumerate(layers):
            print(f"{indent}--- 图层 {i+1}/{len(layers)} ---")
            print_layer_info(layer, current_depth, parent_path)
            print()
                
    except Exception as e:
        print(f"{indent}遍历图层失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def find_smart_object_layers(doc, layer_name: Optional[str] = None, debug: bool = False) -> List:
    """
    递归查找 PSD 中的所有智能对象图层
    
    Args:
        doc: Photoshop 文档对象
        layer_name: 可选，指定要查找的智能对象图层名称（如果为 None 则返回所有智能对象）
        debug: 是否打印详细的调试信息
    
    Returns:
        智能对象图层列表，每个元素包含：
        - layer: 图层对象
        - name: 图层名称
        - path: 图层路径
        - width: 图层宽度（像素）
        - height: 图层高度（像素）
        - bounds: 图层边界信息
    """
    smart_objects = []
    layer_count = 0
    checked_count = 0
    
    def search_layers(layers, parent_path="", depth=0):
        """递归搜索图层"""
        nonlocal layer_count, checked_count
        
        if not layers:
            if debug:
                print(f"{'  ' * depth}[搜索] 图层集合为空或None")
            return
        
        # 确保 layers 是可迭代的
        try:
            layers_list = list(layers) if hasattr(layers, '__iter__') else [layers]
        except:
            if debug:
                print(f"{'  ' * depth}[搜索] 无法将图层集合转换为列表")
            return
        
        if debug:
            print(f"{'  ' * depth}[搜索] 开始检查 {len(layers_list)} 个图层 (路径: {parent_path or '根'})")
        
        for idx, layer in enumerate(layers_list):
            layer_count += 1
            checked_count += 1
            
            try:
                # 获取图层名称
                layer_name_str = None
                try:
                    layer_name_str = layer.name if hasattr(layer, 'name') else None
                    current_path = f"{parent_path}/{layer_name_str}" if parent_path and layer_name_str else (layer_name_str or "未知图层")
                except Exception as e:
                    if debug:
                        print(f"{'  ' * depth}[{idx+1}] 无法获取图层名称: {e}")
                    current_path = "未知图层"
                    layer_name_str = None
                
                if debug:
                    print(f"{'  ' * depth}[{idx+1}/{len(layers_list)}] 检查图层: {layer_name_str or '未知名称'} (路径: {current_path})")
                
                # 检查是否为智能对象（使用多种方法检测）
                is_smart_object = False
                detection_method = None
                detection_details = []  # 记录所有检测方法的详细信息
                
                # 方法1: 检查 layer.kind == LayerKind.SmartObjectLayer
                try:
                    layer_kind = layer.kind
                    kind_str_repr = str(layer_kind)
                    detection_details.append(f"kind={kind_str_repr}")
                    
                    # 获取 LayerKind.SmartObjectLayer 的值进行比较
                    try:
                        so_kind_value = LayerKind.SmartObjectLayer
                        if layer_kind == so_kind_value:
                            is_smart_object = True
                            detection_method = "LayerKind.SmartObjectLayer"
                            if debug:
                                print(f"{'  ' * depth}    ✅ 方法1成功: kind == LayerKind.SmartObjectLayer ({kind_str_repr})")
                        else:
                            if debug:
                                print(f"{'  ' * depth}    ❌ 方法1失败: kind={kind_str_repr}, SmartObjectLayer={so_kind_value}")
                    except Exception as e1:
                        if debug:
                            print(f"{'  ' * depth}    ⚠️ 方法1异常: 无法获取LayerKind.SmartObjectLayer: {e1}")
                except (AttributeError, NameError, TypeError, KeyError) as e:
                    detection_details.append(f"kind=无此属性({type(e).__name__})")
                    if debug:
                        print(f"{'  ' * depth}    ❌ 方法1: 图层没有kind属性")
                except Exception as e:
                    detection_details.append(f"kind=错误({type(e).__name__}: {e})")
                    if debug:
                        print(f"{'  ' * depth}    ❌ 方法1异常: {e}")
                
                # 方法2: 检查 kind 的字符串表示
                if not is_smart_object:
                    try:
                        kind_str = str(layer.kind).lower()
                        detection_details.append(f"kind字符串={kind_str}")
                        if 'smartobject' in kind_str or 'smart object' in kind_str:
                            is_smart_object = True
                            detection_method = f"kind字符串匹配({layer.kind})"
                            if debug:
                                print(f"{'  ' * depth}    ✅ 方法2成功: kind字符串包含'smartobject'")
                        else:
                            if debug:
                                print(f"{'  ' * depth}    ❌ 方法2失败: kind字符串不包含'smartobject'")
                    except Exception as e:
                        if debug:
                            print(f"{'  ' * depth}    ❌ 方法2异常: {e}")
                
                # 方法3: 检查类名
                if not is_smart_object:
                    try:
                        class_name = type(layer).__name__
                        class_name_lower = class_name.lower()
                        detection_details.append(f"类名={class_name}")
                        if 'smart' in class_name_lower and 'object' in class_name_lower:
                            is_smart_object = True
                            detection_method = f"类名匹配({class_name})"
                            if debug:
                                print(f"{'  ' * depth}    ✅ 方法3成功: 类名包含'smart'和'object'")
                        else:
                            if debug:
                                print(f"{'  ' * depth}    ❌ 方法3失败: 类名={class_name}")
                    except Exception as e:
                        if debug:
                            print(f"{'  ' * depth}    ❌ 方法3异常: {e}")
                
                # 方法4: 尝试使用 Photoshop API 的其他方法检测
                if not is_smart_object:
                    try:
                        has_is_smart = hasattr(layer, 'isSmartObject')
                        detection_details.append(f"hasattr(isSmartObject)={has_is_smart}")
                        if has_is_smart:
                            so_value = layer.isSmartObject
                            detection_details.append(f"isSmartObject={so_value}")
                            if so_value:
                                is_smart_object = True
                                detection_method = "isSmartObject属性"
                                if debug:
                                    print(f"{'  ' * depth}    ✅ 方法4成功: isSmartObject=True")
                            else:
                                if debug:
                                    print(f"{'  ' * depth}    ❌ 方法4失败: isSmartObject=False")
                        else:
                            if debug:
                                print(f"{'  ' * depth}    ❌ 方法4: 图层没有isSmartObject属性")
                    except Exception as e:
                        if debug:
                            print(f"{'  ' * depth}    ❌ 方法4异常: {e}")
                
                # 方法5: 检查图层名称是否包含 "SmartObject" 关键字（不区分大小写）
                if not is_smart_object:
                    try:
                        name_str = str(layer_name_str) if layer_name_str else ""
                        detection_details.append(f"图层名称={name_str}")
                        if name_str and 'smartobject' in name_str.lower():
                            is_smart_object = True
                            detection_method = f"图层名称关键字匹配(包含'SmartObject': {name_str})"
                            if debug:
                                print(f"{'  ' * depth}    ✅ 方法5成功: 图层名称包含'SmartObject'")
                        else:
                            if debug:
                                print(f"{'  ' * depth}    ❌ 方法5失败: 图层名称={name_str}")
                    except Exception as e:
                        if debug:
                            print(f"{'  ' * depth}    ❌ 方法5异常: {e}")
                
                # 方法6: 尝试检查图层的所有属性，查找可能包含"smart"的属性
                if not is_smart_object:
                    if debug:
                        try:
                            attrs = [attr for attr in dir(layer) if not attr.startswith('_')]
                            smart_attrs = [attr for attr in attrs if 'smart' in attr.lower()]
                            if smart_attrs:
                                print(f"{'  ' * depth}    💡 方法6: 发现可能相关的属性: {smart_attrs}")
                                # 尝试检查这些属性
                                for attr in smart_attrs:
                                    try:
                                        value = getattr(layer, attr)
                                        print(f"{'  ' * depth}      {attr} = {value}")
                                        if value and (value is True or (isinstance(value, str) and 'smart' in str(value).lower())):
                                            detection_details.append(f"属性{attr}={value}")
                                    except:
                                        pass
                        except:
                            pass
                
                # 如果检测到智能对象，记录信息
                if is_smart_object:
                    if layer_name is None or layer.name == layer_name:
                        # 获取图层尺寸信息
                        # 注意：layer.bounds 可能不准确，实际尺寸会在替换时从智能对象文档获取
                        width = 0
                        height = 0
                        bounds = None
                        
                        try:
                            bounds = layer.bounds
                            if bounds and len(bounds) >= 4:
                                width = int(bounds[2] - bounds[0])  # right - left
                                height = int(bounds[3] - bounds[1])  # bottom - top
                                
                                # 验证bounds计算的尺寸是否合理
                                if width <= 0 or height <= 0:
                                    width = 0
                                    height = 0
                        except Exception:
                            pass
                        
                        # 如果bounds为0，尝试其他方法
                        if width == 0 or height == 0:
                            try:
                                # 尝试使用图层的实际尺寸属性（如果存在）
                                if hasattr(layer, 'width') and hasattr(layer, 'height'):
                                    try:
                                        w = int(layer.width)
                                        h = int(layer.height)
                                        if w > 0 and h > 0:
                                            width = w
                                            height = h
                                    except:
                                        pass
                            except:
                                pass
                        
                        # 记录智能对象信息
                        # 注意：如果尺寸为0，会在替换时从智能对象文档获取真实尺寸
                        smart_objects.append({
                            'layer': layer,
                            'name': layer.name,
                            'path': current_path,
                            'width': width if width > 0 else None,
                            'height': height if height > 0 else None,
                            'bounds': bounds,
                            'detection_method': detection_method,
                            'detection_details': detection_details
                        })
                        if debug:
                            print(f"{'  ' * depth}    🎉 已记录为智能对象! (检测方法: {detection_method})")
                    else:
                        if debug:
                            print(f"{'  ' * depth}    ⏭️ 图层名称不匹配，跳过记录 (期望: {layer_name}, 实际: {layer_name_str})")
                else:
                    if debug:
                        print(f"{'  ' * depth}    ❌ 不是智能对象 (尝试了所有检测方法)")
                        if detection_details:
                            print(f"{'  ' * depth}      检测详情: {', '.join(detection_details)}")
                
                # 如果是图层组（LayerSet），递归搜索子图层
                # LayerSet 有 layers 属性，而 ArtLayer 没有
                # 使用多种方法尝试获取子图层
                has_sub_layers = False
                sub_layers_list = None
                
                # 方法1: 直接访问 layer.layers
                try:
                    if hasattr(layer, 'layers'):
                        sub_layers_list = layer.layers
                        if sub_layers_list:
                            try:
                                sub_count = len(sub_layers_list)
                                if sub_count > 0:
                                    has_sub_layers = True
                                    if debug:
                                        print(f"{'  ' * depth}    📁 发现图层组，包含 {sub_count} 个子图层，开始递归...")
                            except:
                                # 如果无法获取长度，但存在layers属性，也尝试递归
                                has_sub_layers = True
                                if debug:
                                    print(f"{'  ' * depth}    📁 发现图层组（无法获取子图层数量），开始递归...")
                except (AttributeError, NameError, TypeError, KeyError):
                    pass
                except Exception as e:
                    if debug:
                        print(f"{'  ' * depth}    ⚠️ 检查layers属性时出错: {e}")
                
                # 方法2: 尝试通过其他属性访问子图层
                if not has_sub_layers:
                    try:
                        # 某些API可能使用不同的属性名
                        alt_attrs = ['artLayers', 'layerSets', 'children', 'subLayers']
                        for attr in alt_attrs:
                            if hasattr(layer, attr):
                                try:
                                    alt_layers = getattr(layer, attr)
                                    if alt_layers:
                                        try:
                                            if len(alt_layers) > 0:
                                                has_sub_layers = True
                                                sub_layers_list = alt_layers
                                                if debug:
                                                    print(f"{'  ' * depth}    📁 通过属性'{attr}'发现 {len(alt_layers)} 个子图层")
                                                break
                                        except:
                                            pass
                                except:
                                    pass
                    except:
                        pass
                
                # 递归处理子图层
                if has_sub_layers and sub_layers_list:
                    try:
                        search_layers(sub_layers_list, current_path, depth + 1)
                    except Exception as e:
                        if debug:
                            print(f"{'  ' * depth}    ❌ 递归处理子图层时出错: {e}")
                            import traceback
                            traceback.print_exc()
                else:
                    if debug and not is_smart_object:
                        # 尝试判断是否是图层组但无法获取子图层
                        try:
                            layer_type = type(layer).__name__
                            if 'Group' in layer_type or 'Set' in layer_type or 'Folder' in layer_type:
                                print(f"{'  ' * depth}    ⚠️ 可能是图层组 ({layer_type})，但无法获取子图层")
                        except:
                            pass
            except Exception as e:
                # 处理图层时发生的异常
                checked_count -= 1  # 这个图层检查失败，不计入已检查数量
                if debug:
                    print(f"{'  ' * depth}[{idx+1}] ❌ 处理图层时发生异常: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
                # 即使出错也继续处理下一个图层
                continue
    
    # 从文档的顶层图层开始搜索
    if debug:
        print("\n" + "=" * 70)
        print("🔍 开始搜索智能对象图层...")
        print("=" * 70)
    
    try:
        top_layers = doc.layers
        if not top_layers:
            if debug:
                print("⚠️ 文档没有顶层图层")
        else:
            search_layers(top_layers, "", 0)
    except Exception as e:
        if debug:
            print(f"❌ 开始搜索时出错: {e}")
            import traceback
            traceback.print_exc()
    
    # 打印统计信息
    if debug:
        print("\n" + "=" * 70)
        print("📊 搜索统计")
        print("=" * 70)
        print(f"总图层数: {layer_count}")
        print(f"成功检查: {checked_count}")
        print(f"找到智能对象: {len(smart_objects)}")
        if smart_objects:
            print(f"\n找到的智能对象列表:")
            for i, so in enumerate(smart_objects, 1):
                print(f"  [{i}] {so['name']} (路径: {so['path']}, 方法: {so['detection_method']})")
        print("=" * 70 + "\n")
    
    return smart_objects


def replace_smart_object_content(
    session: Session,
    doc,
    layer,
    image_path: Path,
    export_dir: Path,
    tile_size: int = 512,
    resize_mode: str = "contain",
    custom_options: Optional[dict] = None
) -> None:
    """
    替换智能对象图层的内容
    
    Args:
        session: Photoshop 会话对象
        doc: Photoshop 文档对象
        layer: 智能对象图层
        image_path: 新图片路径
        export_dir: 临时文件导出目录
        tile_size: 图片缩放分块尺寸
        resize_mode: 图片缩放模式
            - "stretch": 拉伸填充，不保持宽高比（会变形）
            - "contain": 保持宽高比，完整显示图片（可能有留白，默认）
            - "cover": 保持宽高比，填充目标区域（可能裁剪）
            - "custom": 自定义模式，精确控制位置和尺寸（需要 custom_options）
        custom_options: 自定义模式配置（仅当 resize_mode="custom" 时使用）
    """
    # 设置当前活动图层
    doc.activeLayer = layer
    
    string_id = session.app.stringIDToTypeID
    
    # 编辑智能对象内容
    edit_contents_id = string_id("placedLayerEditContents")
    placed_layer_id = string_id("placedLayer")
    ordinal_id = string_id("ordinal")
    target_enum_id = string_id("targetEnum")
    
    ref = ActionReference()
    ref.putEnumerated(placed_layer_id, ordinal_id, target_enum_id)
    
    desc = ActionDescriptor()
    desc.putReference(string_id("null"), ref)
    
    session.app.executeAction(edit_contents_id, desc, DialogModes.DisplayNoDialogs)
    
    # 获取智能对象文档
    smart_doc = session.active_document
    
    # 获取智能对象文档的真实尺寸
    # 这是智能对象的实际内容尺寸，应该总是有效的
    try:
        target_width = int(smart_doc.width)
        target_height = int(smart_doc.height)
        
        # 验证尺寸是否有效
        if target_width <= 0 or target_height <= 0:
            raise ValueError(f"智能对象文档尺寸无效: {target_width} x {target_height}")
        
        print(f"    智能对象文档尺寸: {target_width} x {target_height} 像素")
    except Exception as e:
        print(f"    ❌ 错误: 无法获取智能对象文档尺寸: {e}")
        raise ValueError(f"无法获取智能对象文档尺寸: {e}")
    
    # 准备缩放后的图片
    from PIL import Image
    with Image.open(image_path) as img:
        # 根据缩放模式决定是否需要保留透明通道
        # contain 和 custom 模式需要透明背景，所以保留透明通道
        # stretch 和 cover 模式可以转换为 RGB
        if resize_mode not in ("contain", "custom"):
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
        
        # 显示原始图片尺寸和比例信息
        orig_width, orig_height = img.size
        orig_ratio = orig_width / orig_height
        target_ratio = target_width / target_height
        
        if resize_mode == "custom" and custom_options:
            # 自定义模式的日志
            position = custom_options.get('position', {})
            size = custom_options.get('size', {})
            print(f"    🎯 自定义模式配置:")
            print(f"       位置: ({position.get('x', 0)}{position.get('unit', 'px')}, {position.get('y', 0)}{position.get('unit', 'px')})")
            print(f"       尺寸: {size.get('width', 0)}{size.get('unit', 'px')} x {size.get('height', 0)}{size.get('unit', 'px')}")
            if size.get('maintain_aspect_ratio', False):
                print(f"       保持宽高比: 是")
        elif resize_mode != "stretch" and abs(orig_ratio - target_ratio) > 0.01:
            print(f"    📐 比例不匹配:")
            print(f"       原始图片: {orig_width} x {orig_height} (比例 {orig_ratio:.3f})")
            print(f"       目标尺寸: {target_width} x {target_height} (比例 {target_ratio:.3f})")
            if resize_mode == "contain":
                print(f"      使用 contain 模式: 保持宽高比，完整显示（留白区域透明）")
            elif resize_mode == "cover":
                print(f"      使用 cover 模式: 保持宽高比，填充区域（可能裁剪）")
        
        resized_img = resize_image_in_tiles(
            img, 
            (target_width, target_height), 
            tile_size,
            mode=resize_mode,
            custom_options=custom_options
        )
        
        # contain 和 custom 模式使用透明背景（RGBA），需要保存为 PNG 格式以保留透明通道
        # 其他模式可以保持原始格式
        if resize_mode in ("contain", "custom") and resized_img.mode == "RGBA":
            resized_path = export_dir / f"{image_path.stem}_resized.png"
        else:
            resized_path = export_dir / f"{image_path.stem}_resized{image_path.suffix}"
        
        resized_img.save(
            resized_path,
            dpi=(int(smart_doc.resolution), int(smart_doc.resolution))
        )
    
    resized_img.close()
    gc.collect()
    
    # 放置新图片
    print(f"    正在放置新图片: {resized_path.name}")
    
    # 确保文件存在
    if not resized_path.exists():
        raise FileNotFoundError(f"缩放后的图片文件不存在: {resized_path}")
    
    # 方法1: 使用 placeEvent 放置图片（替换整个智能对象内容）
    place_desc = ActionDescriptor()
    place_desc.putPath(string_id("null"), str(resized_path))
    place_desc.putBoolean(string_id("antiAlias"), True)
    
    try:
        # 执行放置操作
        session.app.executeAction(string_id("placeEvent"), place_desc, DialogModes.DisplayNoDialogs)
        print(f"    ✅ 图片已放置")
        
        # 等待一下，让 PS 完成放置操作
        import time
        time.sleep(0.8)  # 增加等待时间，确保PS完成处理
        
        # 验证图片是否成功放置
        try:
            # 重新获取智能对象文档（因为放置后可能刷新）
            current_smart_doc = session.active_document
            
            # 检查智能对象文档是否有图层
            if hasattr(current_smart_doc, 'layers') and len(current_smart_doc.layers) > 0:
                print(f"    ✅ 验证: 智能对象文档包含 {len(current_smart_doc.layers)} 个图层")
                # 更新 smart_doc 引用为当前活动文档
                smart_doc = current_smart_doc
            else:
                print(f"    ⚠️ 警告: 智能对象文档可能没有图层")
                
            # 检查文档尺寸是否正常
            if hasattr(current_smart_doc, 'width') and hasattr(current_smart_doc, 'height'):
                doc_width = int(current_smart_doc.width)
                doc_height = int(current_smart_doc.height)
                if doc_width > 0 and doc_height > 0:
                    print(f"    ✅ 验证: 智能对象文档尺寸正常 ({doc_width} x {doc_height})")
                else:
                    print(f"    ⚠️ 警告: 智能对象文档尺寸异常 ({doc_width} x {doc_height})")
                    
        except Exception as e:
            print(f"    ⚠️ 警告: 验证时出错: {e}，但继续执行")
        
        # 重要：确保 smart_doc 引用是最新的活动文档
        # 因为放置操作后，活动文档可能已经更新
        try:
            smart_doc = session.active_document
            print(f"    ✅ 已更新智能对象文档引用")
        except Exception as e:
            print(f"    ⚠️ 警告: 更新文档引用时出错: {e}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"    ❌ 错误: 放置图片失败: {error_msg}")
        print(f"    💡 尝试备用方法...")
        
        # 备用方法：尝试直接使用文件路径
        try:
            # 重新尝试放置
            place_desc2 = ActionDescriptor()
            place_desc2.putPath(string_id("null"), str(resized_path.absolute()))
            place_desc2.putBoolean(string_id("antiAlias"), True)
            session.app.executeAction(string_id("placeEvent"), place_desc2, DialogModes.DisplayNoDialogs)
            print(f"    ✅ 使用备用方法成功放置")
            import time
            time.sleep(0.8)
        except Exception as e2:
            print(f"    ❌ 备用方法也失败: {e2}")
            import traceback
            traceback.print_exc()
            raise
    
    # 关闭智能对象文档并保存更改
    # ⚠️ 重要：不要使用 smart_doc.save()，应该使用 close(PsSaveOptions.psSaveChanges)
    # 因为智能对象是临时文件，不是独立 PSD 文档
    try:
        print(f"    正在关闭智能对象文档并保存更改...")
        
        # 重要：重新获取当前活动文档，确保使用正确的文档引用
        # 因为放置操作后，文档引用可能已经改变
        try:
            current_active_doc = session.active_document
            print(f"    当前活动文档: {current_active_doc.name if hasattr(current_active_doc, 'name') else '未知'}")
            
            # 使用当前活动文档（应该是智能对象文档）
            smart_doc_to_close = current_active_doc
            
            # 验证这确实是智能对象文档（通过检查文档名称或尺寸）
            # 智能对象文档通常是临时文件，名称可能包含 "temp" 或类似标识
            # 或者通过检查文档尺寸是否匹配
            try:
                if hasattr(smart_doc_to_close, 'width') and hasattr(smart_doc_to_close, 'height'):
                    doc_w = int(smart_doc_to_close.width)
                    doc_h = int(smart_doc_to_close.height)
                    if doc_w == target_width and doc_h == target_height:
                        print(f"    ✅ 确认: 活动文档是智能对象文档 ({doc_w} x {doc_h})")
                    else:
                        print(f"    ⚠️ 警告: 文档尺寸不匹配，但继续执行")
            except:
                print(f"    ⚠️ 警告: 无法验证文档，但继续执行")
                
        except Exception as e:
            print(f"    ⚠️ 警告: 获取活动文档时出错: {e}，使用原始 smart_doc")
            smart_doc_to_close = smart_doc
        
        # 保存并关闭智能对象文档
        # 参考 ps_client 的成功实现：使用 executeAction("save") 然后 close()
        import time
        
        print(f"    正在保存智能对象文档...")
        try:
            # 使用 executeAction("save") 来保存，这是 ps_client 中成功的方法
            # 而不是使用 smart_doc.save() 或 close(psSaveChanges)
            save_desc = ActionDescriptor()
            session.app.executeAction(string_id("save"), save_desc, DialogModes.DisplayNoDialogs)
            print(f"    ✅ 智能对象文档已保存 (executeAction方法)")
            
            # 等待一下，确保 PS 完成保存操作
            time.sleep(0.3)
            
        except Exception as save_error:
            save_error_msg = str(save_error)
            print(f"    ⚠️ executeAction('save') 失败: {save_error_msg}")
            # 即使保存失败，也尝试关闭（可能已经自动保存）
            print(f"    继续关闭文档...")
        
        # 关闭智能对象文档（无参数，参考 ps_client 的实现）
        print(f"    正在关闭智能对象文档...")
        try:
            smart_doc_to_close.close()
            print(f"    ✅ 智能对象文档已关闭")
            
            # 等待一下，确保 PS 完成关闭操作并切换回主文档
            time.sleep(0.5)
            
            # 验证是否回到主文档
            try:
                new_active_doc = session.active_document
                if new_active_doc == doc:
                    print(f"    ✅ 确认: 已回到主文档: {doc.name}")
                else:
                    print(f"    ⚠️ 警告: 活动文档可能不是主文档")
                    print(f"    当前活动文档: {new_active_doc.name if hasattr(new_active_doc, 'name') else '未知'}")
                    print(f"    期望主文档: {doc.name}")
            except Exception as e:
                print(f"    ⚠️ 警告: 验证主文档时出错: {e}")
            
            # 清理临时 resized 文件
            try:
                if resized_path.exists():
                    resized_path.unlink()
                    print(f"    🗑️  已清理临时文件: {resized_path.name}")
            except Exception as cleanup_error:
                print(f"    ⚠️ 警告: 清理临时文件失败: {cleanup_error}，但不影响处理结果")
                
        except Exception as close_error:
            close_error_msg = str(close_error)
            print(f"    ❌ 关闭智能对象文档失败: {close_error_msg}")
            import traceback
            traceback.print_exc()
            raise
        
        # 等待一下，让 PS 完成关闭操作并切换回主文档
        import time
        time.sleep(0.8)  # 增加等待时间，确保PS完成操作
        
        # 验证是否回到主文档
        try:
            new_active_doc = session.active_document
            if new_active_doc == doc:
                print(f"    ✅ 已切换回主文档: {doc.name}")
            else:
                print(f"    ⚠️ 警告: 活动文档可能不是主文档")
                print(f"    当前活动文档: {new_active_doc.name if hasattr(new_active_doc, 'name') else '未知'}")
                print(f"    期望主文档: {doc.name}")
        except Exception as e:
            print(f"    ⚠️ 警告: 验证主文档时出错: {e}")
        
    except PermissionError as e:
        error_msg = str(e)
        print(f"\n    ❌ 权限错误: 关闭智能对象文档失败")
        print(f"    错误信息: {error_msg}")
        print(f"\n    💡 解决方案:")
        print(f"    1. 检查 Photoshop 是否以管理员权限运行")
        print(f"    2. 检查 PSD 文件是否被其他程序占用")
        print(f"    3. 检查 PSD 文件所在目录的写入权限")
        raise
    except Exception as e:
        error_msg = str(e)
        # 检查是否是权限相关的错误
        if "permission" in error_msg.lower() or "access" in error_msg.lower() or "denied" in error_msg.lower():
            print(f"\n    ❌ 权限错误: {error_msg}")
            print(f"\n    💡 解决方案:")
            print(f"    1. 以管理员身份运行 Python 脚本")
            print(f"    2. 检查 PSD 文件是否被其他程序占用")
            print(f"    3. 检查文件路径是否包含特殊字符或过长的路径")
            raise
        else:
            print(f"    ⚠️ 警告: 关闭智能对象文档时出错: {e}")
            print(f"    尝试使用备用方法...")
            import traceback
            traceback.print_exc()
            # 尝试使用数值常量
            try:
                smart_doc.close(2)  # 2 = SaveChanges.YES
                print(f"    ✅ 使用备用方法成功关闭")
            except Exception as e2:
                print(f"    ❌ 备用方法也失败: {e2}")
                # 继续执行，因为替换可能已经成功
    
    gc.collect()


def replace_and_export_psd(
    psd_path: Path,
    image_path: Path,
    export_dir: Path,
    smart_object_name: Optional[str] = None,
    output_filename: Optional[str] = None,
    tile_size: int = 512,
    resize_mode: str = "contain",
    custom_options: Optional[dict] = None
) -> Path:
    """
    替换 PSD 中的智能对象并导出图片
    
    Args:
        psd_path: PSD 文件路径
        image_path: 用于替换的图片路径
        export_dir: 导出目录
        smart_object_name: 可选，指定要替换的智能对象名称（如果为 None 则替换第一个找到的智能对象）
        output_filename: 可选，导出文件名（如果为 None 则使用默认名称）
        tile_size: 图片缩放分块尺寸，默认 512
        resize_mode: 图片缩放模式，默认 "contain"
            - "stretch": 拉伸填充，不保持宽高比（会变形）
            - "contain": 保持宽高比，完整显示图片（可能有留白）
            - "cover": 保持宽高比，填充目标区域（可能裁剪）
            - "custom": 自定义模式，精确控制位置和尺寸（需要 custom_options）
        custom_options: 自定义模式配置（仅当 resize_mode="custom" 时使用）
    
    Returns:
        导出的图片文件路径
    """
    # 验证输入
    validate_job_inputs(image_path, psd_path, export_dir)
    
    # ========== 检查权限 ==========
    print("\n" + "=" * 70)
    print("🔐 权限检查")
    print("=" * 70)
    
    # 检查导出目录权限
    has_export_perm, export_perm_error = check_write_permission(export_dir)
    if has_export_perm:
        print(f"✅ 导出目录权限: 正常 ({export_dir})")
    else:
        print(f"❌ 导出目录权限: 失败 - {export_perm_error}")
        print(f"\n💡 解决方案:")
        print(f"  1. 以管理员身份运行 Python 脚本")
        print(f"  2. 修改导出目录为有写入权限的目录")
        print(f"  3. 检查目录是否存在且可访问")
        raise PermissionError(f"导出目录没有写入权限: {export_perm_error}")
    
    # 检查 Photoshop 权限
    has_ps_perm, ps_perm_error = check_photoshop_permissions()
    if has_ps_perm:
        print(f"✅ Photoshop 权限: 正常")
    else:
        print(f"⚠️  Photoshop 权限: {ps_perm_error} (可能不影响使用)")
    
    print("=" * 70)
    
    # ========== 打印素材图基本信息 ==========
    print("\n" + "=" * 70)
    print("📄 素材图信息")
    print("=" * 70)
    from PIL import Image
    with Image.open(image_path) as img:
        img_size = img.size
        img_format = img.format
        img_mode = img.mode
        img_dpi = None
        if hasattr(img, 'info') and 'dpi' in img.info:
            img_dpi = img.info['dpi']
    
    print(f"文件路径: {image_path}")
    print(f"文件大小: {image_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"图片尺寸: {img_size[0]} x {img_size[1]} 像素")
    print(f"图片格式: {img_format}")
    print(f"颜色模式: {img_mode}")
    if img_dpi:
        if isinstance(img_dpi, tuple):
            print(f"分辨率: {img_dpi[0]} x {img_dpi[1]} DPI")
        else:
            print(f"分辨率: {img_dpi} DPI")
    print("=" * 70)
    
    # 确保 Photoshop 正在运行
    ensure_photoshop_running(auto_start=True)
    
    with Session() as session:
        app = session.app
        doc = app.open(str(psd_path))
        
        # 提前查找智能对象图层（用于在PSD文件信息中显示）
        # 如果指定了名称，先查找所有智能对象以便提供更好的错误信息
        # 先尝试普通模式查找
        if smart_object_name:
            all_smart_objects = find_smart_object_layers(doc, None, debug=False)
            smart_objects = find_smart_object_layers(doc, smart_object_name, debug=False)
        else:
            smart_objects = find_smart_object_layers(doc, None, debug=False)
            all_smart_objects = smart_objects  # 没有指定名称时，两者相同
        
        # 如果没找到智能对象，使用调试模式重新查找
        if not smart_objects or not all_smart_objects:
            print("\n⚠️ 第一次查找未找到智能对象，启用详细调试模式重新查找...\n")
            if smart_object_name:
                all_smart_objects = find_smart_object_layers(doc, None, debug=True)
                smart_objects = find_smart_object_layers(doc, smart_object_name, debug=True)
            else:
                smart_objects = find_smart_object_layers(doc, None, debug=True)
                all_smart_objects = smart_objects
        
        # ========== 打印 PSD 文件基本信息 ==========
        print("\n" + "=" * 70)
        print("📋 PSD 文件信息")
        print("=" * 70)
        print(f"文件路径: {psd_path}")
        print(f"文件大小: {psd_path.stat().st_size / 1024 / 1024:.2f} MB")
        print(f"文档名称: {doc.name}")
        print(f"文档尺寸: {int(doc.width)} x {int(doc.height)} 像素")
        print(f"分辨率: {int(doc.resolution)} DPI")
        print(f"颜色模式: {doc.mode}")
        print(f"颜色深度: {doc.bitsPerChannel} bit")
        print(f"图层总数: {len(doc.layers)} (顶层)")
        
        # 显示智能图层统计信息
        print(f"\n智能图层统计:")
        print(f"  智能图层总数: {len(all_smart_objects)}")
        if smart_object_name:
            print(f"  匹配指定名称 '{smart_object_name}' 的图层: {len(smart_objects)}")
            if len(smart_objects) == 0:
                if all_smart_objects:
                    available_names = [so['name'] for so in all_smart_objects]
                    print(f"  所有智能图层名称: {', '.join(available_names)}")
        else:
            print(f"  将处理的图层数: {len(smart_objects)}")
        
        # 显示智能图层列表（简要信息）
        if all_smart_objects:
            print(f"\n智能图层列表:")
            for i, so in enumerate(all_smart_objects, 1):
                name = so['name']
                path = so['path']
                width = so['width'] if so['width'] else '?'
                height = so['height'] if so['height'] else '?'
                detection_method = so.get('detection_method', '未知方法')
                
                # 标记是否会被处理
                # 检查当前图层是否在将要处理的列表中
                will_process = ""
                if any(s['name'] == name and s['path'] == path for s in smart_objects):
                    will_process = " ⭐ 将处理"
                elif smart_object_name:
                    will_process = " ⏭️ 跳过 (名称不匹配)"
                
                print(f"  [{i}] {name} {will_process}")
                print(f"      路径: {path}")
                print(f"      尺寸: {width} x {height} 像素")
                print(f"      检测方法: {detection_method}")
        else:
            print(f"  ⚠️ 未找到任何智能图层")
        
        print("=" * 70)
        
        # 验证智能对象是否存在
        if not smart_objects:
            # 如果没找到智能对象，打印调试信息
            print("\n" + "=" * 70)
            print("⚠️  未找到智能对象图层 - 开始调试模式")
            print("=" * 70)
            print("正在打印所有图层信息以帮助排查问题...\n")
            try:
                debug_print_all_layers(doc, max_depth=5)
            except Exception as e:
                print(f"调试信息打印失败: {e}")
                import traceback
                traceback.print_exc()
            print("\n" + "=" * 70)
            
            doc.close()
            if all_smart_objects:
                available_names = [so['name'] for so in all_smart_objects]
                raise ValueError(
                    f"未找到名为 '{smart_object_name}' 的智能对象图层。\n"
                    f"可用的智能对象名称: {', '.join(available_names)}\n"
                    f"提示: 如果不指定 smart_object_name，将自动使用第一个找到的智能对象"
                )
            else:
                error_msg = (
                    "PSD 文件中没有找到任何智能对象图层。\n"
                    "可能的原因：\n"
                    "1. PSD 文件中确实没有智能对象图层\n"
                    "2. 智能对象的类型标识与程序检测方法不匹配\n"
                    "3. 图层被嵌套在特殊的图层组中\n"
                    "\n"
                    "已在上方打印了所有图层的调试信息，请检查：\n"
                    "- 图层的 kind 值\n"
                    "- 图层的类型名称\n"
                    "- 是否存在包含 'Smart' 或 'smart' 的标识"
                )
                raise ValueError(error_msg)
        
        # ========== 打印智能对象详细信息 ==========
        print("\n" + "=" * 70)
        print("🔗 智能对象详细信息")
        print("=" * 70)
        print(f"将处理 {len(smart_objects)} 个智能对象图层:")
        for i, so in enumerate(smart_objects, 1):
            print(f"\n  [{i}/{len(smart_objects)}] {so['name']}")
            print(f"      图层路径: {so['path']}")
            
            # 显示尺寸信息
            if so['width'] and so['height'] and so['width'] > 0 and so['height'] > 0:
                print(f"      图层尺寸: {so['width']} x {so['height']} 像素")
            else:
                print(f"      图层尺寸: 未知 (将在替换时从智能对象文档获取)")
            
            # 显示位置信息（bounds）
            if so['bounds']:
                try:
                    bounds = so['bounds']
                    left = int(bounds[0])
                    top = int(bounds[1])
                    right = int(bounds[2])
                    bottom = int(bounds[3])
                    print(f"      图层位置: 左上角 ({left}, {top})")
                    print(f"      图层边界: ({left}, {top}) -> ({right}, {bottom})")
                    print(f"      实际尺寸: {right - left} x {bottom - top} 像素 (从bounds计算)")
                except Exception as e:
                    print(f"      图层位置: 未知 (解析bounds失败: {e})")
            else:
                print(f"      图层位置: 未知 (无bounds信息)")
            
            # 显示检测方法
            detection_method = so.get('detection_method', '未知方法')
            print(f"      检测方法: {detection_method}")
            
            # 显示处理标记
            if smart_object_name:
                print(f"      处理状态: ⭐ 已匹配指定名称 '{smart_object_name}'")
            else:
                print(f"      处理状态: ⭐ 将自动处理")
        print("=" * 70)
        
        # ========== 打印替换信息 ==========
        print("\n" + "=" * 70)
        print("🔄 开始处理")
        print("=" * 70)
        print(f"将处理 {len(smart_objects)} 个智能对象")
        print(f"素材图尺寸: {img_size[0]} x {img_size[1]} 像素")
        resize_mode_desc = {
            "stretch": "拉伸填充（会变形）",
            "contain": "保持宽高比，完整显示（可能有留白）",
            "cover": "保持宽高比，填充区域（可能裁剪）",
            "custom": "自定义模式（精确控制位置和尺寸）"
        }
        print(f"缩放策略: {resize_mode_desc.get(resize_mode, resize_mode)}")
        print(f"分块尺寸: {tile_size} 像素")
        print("=" * 70)
        
        # 处理所有智能对象
        processed_count = 0
        for i, so in enumerate(smart_objects, 1):
            print(f"\n⏳ [{i}/{len(smart_objects)}] 正在替换智能对象: {so['name']}...")
            try:
                replace_smart_object_content(
                    session,
                    doc,
                    so['layer'], 
                    image_path, 
                    export_dir, 
                    tile_size,
                    resize_mode,
                    custom_options
                )
                print(f"✅ [{i}/{len(smart_objects)}] 智能对象 '{so['name']}' 已替换")
                processed_count += 1
                
                # 确保回到主文档（每个替换操作后）
                try:
                    import time
                    time.sleep(0.3)
                    current_active = session.active_document
                    if current_active != doc:
                        doc.activeLayer = so['layer']
                        print(f"    ✅ 已确保回到主文档")
                except Exception as e:
                    print(f"    ⚠️ 警告: 检查主文档时出错: {e}")
                    
            except Exception as e:
                print(f"❌ [{i}/{len(smart_objects)}] 处理智能对象 '{so['name']}' 时出错: {e}")
                import traceback
                traceback.print_exc()
                # 继续处理下一个智能对象
                continue
        
        print(f"\n✅ 处理完成: 成功处理 {processed_count}/{len(smart_objects)} 个智能对象")
        
        # 确保活动文档是主文档（而不是智能对象文档）
        try:
            # 等待一下，确保智能对象文档已关闭
            import time
            time.sleep(0.3)
            
            # 如果智能对象文档还没关闭，确保回到主文档
            current_active = session.active_document
            if current_active != doc:
                print(f"    ⚠️ 警告: 活动文档不是主文档，尝试切换...")
                try:
                    # 尝试激活主文档
                    # 注意：在 photoshop-python-api 中，关闭智能对象后应该自动回到主文档
                    # 如果不行，可能需要其他方法
                    # 使用第一个智能对象图层来激活主文档
                    if smart_objects:
                        doc.activeLayer = smart_objects[0]['layer']
                        print(f"    ✅ 已激活主文档和目标图层")
                except Exception as e:
                    print(f"    ⚠️ 警告: 切换文档时出错: {e}")
            else:
                print(f"    ✅ 确认: 活动文档是主文档")
        except Exception as e:
            print(f"    ⚠️ 警告: 检查活动文档时出错: {e}")
        
        # 导出图片
        if output_filename is None:
            output_filename = f"{psd_path.stem}_export.png"
        
        export_path = export_dir / output_filename
        
        # 检查导出路径的权限
        print(f"\n⏳ 正在导出图片...")
        has_permission, perm_error = check_write_permission(export_path)
        if not has_permission:
            print(f"\n    ❌ 权限检查失败: {perm_error}")
            print(f"\n    💡 解决方案:")
            print(f"    1. 以管理员身份运行 Python 脚本")
            print(f"    2. 修改导出目录为有写入权限的目录（如用户文档目录）")
            print(f"    3. 检查导出目录是否存在且可访问: {export_dir}")
            print(f"    4. 在 Windows 上，尝试右键 Python/终端 -> 以管理员身份运行")
            
            # 建议使用用户目录作为导出目录
            try:
                user_docs = Path.home() / "Documents"
                if user_docs.exists() and os.access(user_docs, os.W_OK):
                    print(f"\n    💡 建议使用用户文档目录: {user_docs}")
            except:
                pass
            
            raise PermissionError(f"导出路径没有写入权限: {perm_error}")
        
        print(f"    ✅ 权限检查通过")
        
        try:
            # 确保导出目录存在
            try:
                export_path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                raise PermissionError(f"无法创建导出目录: {export_path.parent}, 错误: {e}")
            
            options = session.ExportOptionsSaveForWeb()
            print(f"    导出路径: {export_path}")
            doc.exportDocument(
                str(export_path),
                exportAs=session.ExportType.SaveForWeb,
                options=options
            )
            print(f"    ✅ 导出成功")
        except PermissionError as e:
            print(f"\n❌ 权限错误: 导出失败")
            print(f"    错误信息: {e}")
            print(f"\n    💡 解决方案:")
            print(f"    1. 以管理员身份运行 Python 脚本或终端")
            print(f"    2. 检查导出目录的写入权限")
            print(f"    3. 确保导出文件没有被其他程序占用")
            print(f"    4. 尝试使用不同的导出路径")
            import traceback
            traceback.print_exc()
            try:
                doc.close()
            except:
                pass
            raise
        except Exception as e:
            error_msg = str(e)
            if "permission" in error_msg.lower() or "access" in error_msg.lower() or "denied" in error_msg.lower():
                print(f"\n❌ 权限错误: 导出失败")
                print(f"    错误信息: {error_msg}")
                print(f"\n    💡 解决方案:")
                print(f"    1. 以管理员身份运行 Python 脚本")
                print(f"    2. 检查导出路径: {export_path}")
                print(f"    3. 确保 Photoshop 有写入权限")
            else:
                print(f"\n❌ 导出失败: {e}")
            import traceback
            traceback.print_exc()
            try:
                doc.close()
            except:
                pass
            raise
        
        print(f"\n" + "=" * 70)
        print("✅ 处理完成")
        print("=" * 70)
        print(f"导出路径: {export_path}")
        if export_path.exists():
            print(f"文件大小: {export_path.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print(f"⚠️ 警告: 导出文件不存在，请检查导出路径和权限")
        print("=" * 70)
        
        # 关闭主文档
        try:
            doc.close()
            print(f"主文档已关闭")
        except Exception as e:
            print(f"⚠️ 警告: 关闭主文档时出错: {e}")
    
    gc.collect()
    return export_path


def process_psd_with_image(
    psd_path: str | Path,
    image_path: str | Path,
    config: dict | None = None
) -> Path:
    """
    封装函数：处理 PSD 套图，替换智能对象并导出
    
    Args:
        psd_path: PSD 套图文件路径（字符串或 Path 对象）
        image_path: 素材图片路径（字符串或 Path 对象）
        config: 配置字典，可选参数：
            - export_dir: 导出目录（必需）
            - smart_object_name: 智能对象图层名称（可选，默认替换第一个找到的）
            - output_filename: 导出文件名（可选，默认使用 PSD 文件名_export.png）
            - tile_size: 图片缩放分块尺寸（可选，默认 512）
            - resize_mode: 图片缩放模式（可选，默认 "contain"）
                - "stretch": 拉伸填充，不保持宽高比（会变形）
                - "contain": 保持宽高比，完整显示图片（可能有留白）
                - "cover": 保持宽高比，填充目标区域（可能裁剪）
                - "custom": 自定义模式，精确控制位置和尺寸（需要 custom_options）
            - custom_options: 自定义模式配置（仅当 resize_mode="custom" 时使用）
            - auto_start_photoshop: 是否自动启动 Photoshop（可选，默认 True）
            - verbose: 是否显示详细信息（可选，默认 True）
    
    Returns:
        导出的图片文件路径
    
    Example:
        >>> config = {
        ...     'export_dir': 'D:/output',
        ...     'smart_object_name': '图片',
        ...     'output_filename': 'result.png',
        ...     'tile_size': 512
        ... }
        >>> result = process_psd_with_image(
        ...     psd_path='D:/templates/template.psd',
        ...     image_path='D:/images/image.jpg',
        ...     config=config
        ... )
    """
    # 转换路径类型
    psd_path = Path(psd_path)
    image_path = Path(image_path)
    
    # 默认配置
    default_config = {
        'export_dir': None,  # 必需参数
        'smart_object_name': None,
        'output_filename': None,
        'tile_size': 512,
        'resize_mode': 'contain',  # 默认保持宽高比，完整显示
        'custom_options': None,  # 自定义模式配置
        'auto_start_photoshop': True,
        'verbose': True
    }
    
    # 合并配置
    if config is None:
        config = {}
    
    final_config = {**default_config, **config}
    
    # 验证必需参数
    if final_config['export_dir'] is None:
        raise ValueError("config['export_dir'] 是必需参数，请提供导出目录路径")
    
    export_dir = Path(final_config['export_dir'])
    
    # 如果 verbose 为 False，临时禁用 print（通过重定向）
    import io
    import contextlib
    
    if not final_config['verbose']:
        # 创建一个空的输出流来抑制打印
        null_stream = io.StringIO()
        with contextlib.redirect_stdout(null_stream), contextlib.redirect_stderr(null_stream):
            return replace_and_export_psd(
                psd_path=psd_path,
                image_path=image_path,
                export_dir=export_dir,
                smart_object_name=final_config['smart_object_name'],
                output_filename=final_config['output_filename'],
                tile_size=final_config['tile_size'],
                resize_mode=final_config['resize_mode'],
                custom_options=final_config.get('custom_options')
            )
    else:
        return replace_and_export_psd(
            psd_path=psd_path,
            image_path=image_path,
            export_dir=export_dir,
            smart_object_name=final_config['smart_object_name'],
            output_filename=final_config['output_filename'],
            tile_size=final_config['tile_size'],
            resize_mode=final_config['resize_mode'],
            custom_options=final_config.get('custom_options')
        )


def main():
    """主函数 - 可以通过命令行参数或直接修改代码中的路径来使用"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="替换 PSD 中的智能对象并导出图片"
    )
    parser.add_argument(
        "--psd",
        type=str,
        help="PSD 文件路径"
    )
    parser.add_argument(
        "--image",
        type=str,
        help="用于替换的图片路径"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="导出目录"
    )
    parser.add_argument(
        "--smart-object-name",
        type=str,
        default=None,
        help="可选：指定要替换的智能对象图层名称（如果未指定则替换第一个找到的智能对象）"
    )
    parser.add_argument(
        "--output-filename",
        type=str,
        default=None,
        help="可选：导出文件名（如果未指定则使用默认名称）"
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=512,
        help="图片缩放分块尺寸，默认 512"
    )
    
    args = parser.parse_args()
    
    # 如果提供了命令行参数，使用命令行参数
    if args.psd and args.image and args.output_dir:
        psd_path = Path(args.psd)
        image_path = Path(args.image)
        export_dir = Path(args.output_dir)
    else:
        # 否则，使用代码中定义的路径（可以在这里直接修改）
        # ========== 在这里修改路径 ==========
        psd_path = Path(r"D:\workspace\yishe-ps\examples\template.psd")  # 修改为你的 PSD 路径
        image_path = Path(r"D:\workspace\yishe-ps\examples\re.jpg")      # 修改为你的图片路径
        export_dir = Path(r"D:\workspace\yishe-ps\output")               # 修改为导出目录
        # ===================================
        
        # 检查路径是否有效
        if not psd_path.exists() or not image_path.exists():
            print("❌ 错误: 请通过命令行参数提供路径，或在代码中修改路径")
            print("\n使用示例:")
            print("  python -m src.psd-img-replace-smartobject --psd path/to/file.psd --image path/to/image.jpg --output-dir path/to/output")
            sys.exit(1)
    
    try:
        export_path = replace_and_export_psd(
            psd_path=psd_path,
            image_path=image_path,
            export_dir=export_dir,
            smart_object_name=args.smart_object_name,
            output_filename=args.output_filename,
            tile_size=args.tile_size
        )
        print(f"\n✅ 处理完成！导出文件: {export_path}")
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

