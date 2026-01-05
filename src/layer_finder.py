"""
图层查找模块
包含查找智能对象、画板等图层的功能
"""
import sys
from pathlib import Path
from typing import Optional, List

from photoshop.api.enumerations import LayerKind

# 支持相对导入和绝对导入
try:
    from .services.psd_analysis_service import analyze_psd
except ImportError:
    try:
        from src.services.psd_analysis_service import analyze_psd
    except ImportError:
        analyze_psd = None


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


def find_artboard_layers(doc, psd_path: Optional[Path] = None, debug: bool = False) -> List:
    """
    查找 PSD 中的所有画板图层
    
    Args:
        doc: Photoshop 文档对象
        psd_path: PSD 文件路径（可选，如果提供则使用分析服务获取画板信息）
        debug: 是否打印调试信息
    
    Returns:
        画板图层列表，每个元素包含：
        - layer: 图层对象
        - name: 图层名称
        - path: 图层路径
    """
    artboards = []
    
    # 方法1: 如果提供了 psd_path，使用分析服务获取画板信息，然后在 PS 中查找对应图层
    if psd_path and analyze_psd:
        try:
            if debug:
                print(f"  📋 方法1: 使用分析服务查找画板")
                print(f"    分析 PSD 文件: {psd_path}")
            
            analysis_result = analyze_psd(psd_path)
            layer_structure = analysis_result.get('layer_structure', [])
            statistics = analysis_result.get('statistics', {})
            artboard_count = statistics.get('artboard_count', 0)
            
            if debug:
                print(f"    分析结果: 统计显示有 {artboard_count} 个画板")
                print(f"    图层结构数量: {len(layer_structure)}")
            
            # 从分析结果中提取画板名称
            artboard_names = []
            def extract_artboards(layers, parent_path=""):
                for layer_info in layers:
                    if layer_info.get('is_artboard', False):
                        artboard_names.append({
                            'name': layer_info.get('name', ''),
                            'path': layer_info.get('path', '')
                        })
                        if debug:
                            print(f"      找到画板: {layer_info.get('name', '')} (路径: {layer_info.get('path', '')})")
                    if layer_info.get('children'):
                        extract_artboards(layer_info['children'], layer_info.get('path', ''))
            
            extract_artboards(layer_structure)
            
            if artboard_names:
                if debug:
                    print(f"    ✅ 从分析服务找到 {len(artboard_names)} 个画板")
                    print(f"    画板列表:")
                    for i, ab_info in enumerate(artboard_names, 1):
                        print(f"      [{i}] {ab_info['name']} (路径: {ab_info['path']})")
                
                # 在 Photoshop 文档中按名称查找对应的图层
                def find_layer_by_name(layers, target_name):
                    """递归查找指定名称的图层"""
                    for layer in layers:
                        try:
                            layer_name = layer.name if hasattr(layer, 'name') else ""
                            if layer_name == target_name:
                                return layer
                            # 如果是图层组，递归搜索
                            if hasattr(layer, 'layers') and layer.layers:
                                found = find_layer_by_name(layer.layers, target_name)
                                if found:
                                    return found
                        except Exception as e:
                            if debug:
                                print(f"查找图层时出错: {e}")
                            continue
                    return None
                
                # 获取所有顶层图层
                top_layers = []
                try:
                    if hasattr(doc, 'layers'):
                        top_layers = list(doc.layers) if hasattr(doc.layers, '__iter__') else [doc.layers]
                    elif hasattr(doc, '__iter__'):
                        top_layers = list(doc)
                except Exception as e:
                    if debug:
                        print(f"获取顶层图层时出错: {e}")
                
                # 查找每个画板对应的图层
                if debug:
                    print(f"    🔍 开始在 Photoshop 文档中查找对应的图层...")
                    print(f"    顶层图层数量: {len(top_layers)}")
                
                for artboard_info in artboard_names:
                    artboard_name = artboard_info['name']
                    artboard_path = artboard_info['path']
                    
                    if debug:
                        print(f"    🔎 查找画板图层: '{artboard_name}'")
                    
                    # 尝试在顶层图层中查找（画板通常是顶层图层组）
                    found_layer = None
                    try:
                        # 先检查顶层图层
                        if debug:
                            print(f"      检查 {len(top_layers)} 个顶层图层...")
                        for idx, layer in enumerate(top_layers):
                            try:
                                layer_name = layer.name if hasattr(layer, 'name') else ""
                                if debug and idx < 5:  # 只打印前5个，避免日志过多
                                    print(f"        图层[{idx}]: '{layer_name}'")
                                if layer_name == artboard_name:
                                    found_layer = layer
                                    if debug:
                                        print(f"      ✅ 在顶层图层中找到匹配: '{layer_name}'")
                                    break
                            except Exception as e:
                                if debug:
                                    print(f"        检查图层[{idx}]时出错: {e}")
                                continue
                        
                        # 如果顶层没找到，递归搜索
                        if not found_layer:
                            if debug:
                                print(f"      顶层未找到，开始递归搜索...")
                            found_layer = find_layer_by_name(top_layers, artboard_name)
                            if found_layer:
                                if debug:
                                    print(f"      ✅ 递归搜索找到图层")
                    except Exception as e:
                        if debug:
                            print(f"      ❌ 查找画板图层 '{artboard_name}' 时出错: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    if found_layer:
                        artboards.append({
                            'layer': found_layer,
                            'name': artboard_name,
                            'path': artboard_path
                        })
                        if debug:
                            print(f"      ✅ 成功找到画板图层: {artboard_name} (路径: {artboard_path})")
                    else:
                        if debug:
                            print(f"      ⚠️ 警告: 未在 Photoshop 文档中找到画板图层 '{artboard_name}'")
                            print(f"        画板路径: {artboard_path}")
                            print(f"        可能原因:")
                            print(f"          1. 图层名称不匹配")
                            print(f"          2. 画板不在顶层图层中")
                            print(f"          3. Photoshop 文档结构与分析结果不一致")
                
                if artboards:
                    if debug:
                        print(f"    ✅ 方法1成功: 找到 {len(artboards)} 个画板图层")
                    return artboards
                else:
                    if debug:
                        print(f"    ⚠️ 方法1: 分析服务找到画板，但未在 Photoshop 中找到对应图层")
            else:
                if debug:
                    print(f"    ⚠️ 方法1: 分析服务未找到画板")
        except Exception as e:
            if debug:
                print(f"    ❌ 方法1失败: 使用分析服务查找画板时出错: {e}")
                import traceback
                traceback.print_exc()
                print(f"    将尝试方法2: 直接在 Photoshop 文档中搜索")
    
    # 方法2: 直接在 Photoshop 文档中搜索画板（备用方法）
    if debug:
        print(f"  📋 方法2: 直接在 Photoshop 文档中搜索画板属性")
    
    def search_artboards(layers, parent_path="", depth=0):
        """递归搜索画板"""
        for layer in layers:
            try:
                layer_name = layer.name if hasattr(layer, 'name') else "未知图层"
                current_path = f"{parent_path}/{layer_name}" if parent_path else layer_name
                
                # 检查是否是画板
                is_artboard = False
                detection_method = None
                try:
                    # 方法1: 检查是否有 artboard 属性
                    if hasattr(layer, 'artboard') and layer.artboard:
                        is_artboard = True
                        detection_method = "artboard 属性"
                    # 方法2: 检查是否有 is_artboard 属性
                    elif hasattr(layer, 'is_artboard') and getattr(layer, 'is_artboard'):
                        is_artboard = True
                        detection_method = "is_artboard 属性"
                    # 方法3: 检查图层类型
                    elif hasattr(layer, 'kind'):
                        kind_str = str(layer.kind).lower()
                        if 'artboard' in kind_str:
                            is_artboard = True
                            detection_method = f"kind 属性 ({layer.kind})"
                except Exception as e:
                    if debug and depth == 0:  # 只打印顶层图层的错误，避免日志过多
                        print(f"      检查图层 '{layer_name}' 时出错: {e}")
                
                if is_artboard:
                    artboards.append({
                        'layer': layer,
                        'name': layer_name,
                        'path': current_path
                    })
                    if debug:
                        print(f"      ✅ 找到画板: {layer_name} (路径: {current_path}, 方法: {detection_method})")
                
                # 如果是图层组，递归搜索
                if hasattr(layer, 'layers') and layer.layers:
                    search_artboards(layer.layers, current_path, depth + 1)
            except Exception as e:
                if debug and depth == 0:
                    print(f"      处理图层时出错: {e}")
                continue
    
    try:
        if hasattr(doc, 'layers'):
            if debug:
                print(f"    从 doc.layers 开始搜索...")
            search_artboards(doc.layers, "", 0)
        elif hasattr(doc, '__iter__'):
            if debug:
                print(f"    从 doc 迭代器开始搜索...")
            search_artboards(list(doc), "", 0)
        else:
            if debug:
                print(f"    ⚠️ 文档没有 layers 属性或迭代器")
    except Exception as e:
        if debug:
            print(f"    ❌ 搜索画板时出错: {e}")
            import traceback
            traceback.print_exc()
    
    if debug:
        if artboards:
            print(f"  ✅ 方法2成功: 找到 {len(artboards)} 个画板")
        else:
            print(f"  ⚠️ 方法2: 未找到画板")
    
    return artboards


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













