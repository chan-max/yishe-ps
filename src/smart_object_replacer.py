"""
智能对象替换模块
包含替换智能对象内容的核心逻辑
"""
import gc
import time
from pathlib import Path
from typing import Optional

from photoshop import Session
from photoshop.api import ActionDescriptor, ActionReference
from photoshop.api.enumerations import DialogModes, LayerKind

# 支持相对导入和绝对导入
try:
    from .utils import resize_image_in_tiles
except ImportError:
    try:
        from src.utils import resize_image_in_tiles
    except ImportError:
        raise ImportError("无法导入 resize_image_in_tiles")


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
        # 保留透明通道：RGBA、LA 模式保持原样，P 模式如果有透明通道则转换为 RGBA
        # 只有不包含透明通道的图片才转换为 RGB
        if img.mode == "P":
            # 调色板模式：检查是否有透明通道
            if "transparency" in img.info:
                img = img.convert("RGBA")
            else:
                # 如果没有透明通道，根据模式决定是否转换为 RGB
                if resize_mode not in ("contain", "custom"):
                    img = img.convert("RGB")
        elif img.mode == "LA":
            # LA 模式（灰度+透明）：转换为 RGBA 以保持透明通道
            img = img.convert("RGBA")
        elif img.mode == "RGBA":
            # RGBA 模式保持不变，直接使用（所有模式都保留透明通道）
            pass
        # RGB 等其他模式保持不变
        
        # 显示原始图片尺寸和比例信息
        orig_width, orig_height = img.size
        orig_ratio = orig_width / orig_height
        target_ratio = target_width / target_height
        
        if resize_mode == "custom" and custom_options:
            # 自定义模式的日志
            position = custom_options.get('position', {})
            size = custom_options.get('size', {})
            child_resize_mode = custom_options.get('child_resize_mode', 'contain')
            print(f"    🎯 自定义模式配置:")
            print(f"       位置: ({position.get('x', 0)}{position.get('unit', 'px')}, {position.get('y', 0)}{position.get('unit', 'px')})")
            print(f"       尺寸: {size.get('width', 0)}{size.get('unit', 'px')} x {size.get('height', 0)}{size.get('unit', 'px')}")
            print(f"       区域缩放模式: {child_resize_mode} ({'铺满裁剪' if child_resize_mode == 'cover' else '完整显示'})")
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
        
        # 如果图片有透明通道（RGBA 模式），保存为 PNG 格式以保留透明通道
        # 其他模式可以保持原始格式
        if resized_img.mode == "RGBA":
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
    
    # 检查智能对象文档中是否有图层，处理旧图层
    # 策略：优先使用 placeEvent 替换第一个图层内容，然后删除多余的图层
    try:
        if hasattr(smart_doc, 'layers') and len(smart_doc.layers) > 0:
            layer_count = len(smart_doc.layers)
            print(f"    智能对象文档当前有 {layer_count} 个图层")
            
            # 选择第一个图层，placeEvent 会替换它的内容
            first_layer = smart_doc.layers[0]
            smart_doc.activeLayer = first_layer
            print(f"    ✅ 已选择第一个图层，placeEvent 将替换其内容")
            
            # 如果有多个图层，尝试删除多余的图层（从后往前删除）
            if layer_count > 1:
                print(f"    📋 检测到 {layer_count} 个图层，将尝试删除多余的图层")
                
                # 辅助函数：检查图层是否可以删除
                def can_delete_layer(layer):
                    """检查图层是否可以删除"""
                    try:
                        # 检查是否是背景图层
                        if hasattr(layer, 'kind'):
                            # kind 为 LayerKind.BackgroundLayer 表示背景图层
                            if layer.kind == LayerKind.BackgroundLayer:
                                return False, "背景图层"
                        # 检查是否被锁定
                        if hasattr(layer, 'allLocked') and layer.allLocked:
                            return False, "图层被锁定"
                        return True, "可删除"
                    except Exception as e:
                        # 如果检查失败，默认允许尝试删除（让删除操作自己判断）
                        return True, f"检查失败({str(e)[:50]})，尝试删除"
                
                # 从后往前删除多余的图层（保留第一个）
                deleted_count = 0
                for i in range(layer_count - 1, 0, -1):  # 从最后一个到第二个
                    try:
                        layer = smart_doc.layers[i]
                        can_delete, reason = can_delete_layer(layer)
                        
                        if not can_delete:
                            print(f"    ⚠️ 跳过图层 {i+1}: {reason}，无法删除")
                            continue
                        
                        # 尝试删除
                        try:
                            # 方法1: 使用 ActionDescriptor
                            delete_id = string_id("delete")
                            layer_ref = ActionReference()
                            layer_ref.putIndex(string_id("layer"), i + 1)  # PS索引从1开始
                            
                            delete_desc = ActionDescriptor()
                            delete_desc.putReference(string_id("null"), layer_ref)
                            
                            session.app.executeAction(delete_id, delete_desc, DialogModes.DisplayNoDialogs)
                            deleted_count += 1
                            print(f"    ✅ 已删除图层 {i+1}/{layer_count}")
                        except Exception as e1:
                            # 方法2: 直接调用 delete 方法
                            try:
                                if hasattr(layer, 'delete'):
                                    layer.delete()
                                    deleted_count += 1
                                    print(f"    ✅ 使用备用方法删除图层 {i+1}")
                                else:
                                    print(f"    ⚠️ 图层 {i+1} 无法删除: 没有 delete 方法")
                            except Exception as e2:
                                print(f"    ⚠️ 图层 {i+1} 无法删除: {e2}")
                        
                        # 等待一下，让PS完成删除操作
                        time.sleep(0.2)
                        
                    except Exception as e:
                        print(f"    ⚠️ 警告: 处理图层 {i+1} 时出错: {e}")
                        continue
                
                print(f"    ✅ 已删除 {deleted_count}/{layer_count-1} 个多余图层")
            else:
                print(f"    ✅ 只有一个图层，将直接替换其内容")
    except Exception as e:
        print(f"    ⚠️ 警告: 处理图层时出错: {e}，继续执行替换")
    
    # 方法1: 使用 placeEvent 放置图片（替换选中图层的内容）
    # 注意：如果选中了图层，placeEvent 会替换该图层的内容，而不是创建新图层
    # 如果第一个图层是背景图层，placeEvent 会创建新图层
    place_desc = ActionDescriptor()
    place_desc.putPath(string_id("null"), str(resized_path))
    place_desc.putBoolean(string_id("antiAlias"), True)
    
    try:
        # 执行放置操作（会替换选中图层的内容，或创建新图层）
        session.app.executeAction(string_id("placeEvent"), place_desc, DialogModes.DisplayNoDialogs)
        print(f"    ✅ 图片已放置（替换选中图层内容）")
        
        # 等待一下，让 PS 完成放置操作
        time.sleep(0.8)  # 增加等待时间，确保PS完成处理
        
        # 验证图片是否成功放置
        try:
            # 重新获取智能对象文档（因为放置后可能刷新）
            current_smart_doc = session.active_document
            
            # 检查智能对象文档是否有图层
            if hasattr(current_smart_doc, 'layers') and len(current_smart_doc.layers) > 0:
                layer_count = len(current_smart_doc.layers)
                print(f"    ✅ 验证: 智能对象文档包含 {layer_count} 个图层")
                
                # 确保新放置的图层可见（placeEvent 应该会替换内容，但为了确保显示，检查图层可见性）
                try:
                    # 检查所有图层的可见性，确保新图层可见
                    for i, layer in enumerate(current_smart_doc.layers):
                        if hasattr(layer, 'visible'):
                            if not layer.visible:
                                print(f"    ⚠️ 警告: 图层 {i+1} 不可见，设置为可见")
                                layer.visible = True
                except Exception as vis_error:
                    print(f"    ⚠️ 警告: 检查图层可见性时出错: {vis_error}，但继续执行")
                
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

