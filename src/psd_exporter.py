"""
PSD 导出模块
包含多画板导出等复杂导出逻辑
"""
import re
import time
from pathlib import Path
from typing import Optional, List

from photoshop import Session

# 支持相对导入和绝对导入
try:
    from .utils.permission_utils import check_write_permission
    from .layer_finder import find_artboard_layers
    from .smart_object_replacer import replace_smart_object_content
    from .utils import create_photoshop_session
    from .layer_finder import find_smart_object_layers
except ImportError:
    try:
        from src.utils.permission_utils import check_write_permission
        from src.layer_finder import find_artboard_layers
        from src.smart_object_replacer import replace_smart_object_content
        from src.utils import create_photoshop_session
        from src.layer_finder import find_smart_object_layers
    except ImportError:
        raise ImportError("无法导入必要的模块")


def replace_and_export_psd_multi(
    psd_path: Path,
    export_dir: Path,
    smart_objects_config: list[dict],
    output_filename: Optional[str] = None
) -> List[Path]:
    """
    处理 PSD 文件，支持多个智能对象的不同配置
    
    Args:
        psd_path: PSD 文件路径
        export_dir: 导出目录
        smart_objects_config: 智能对象配置数组
        output_filename: 导出文件名（可选）
    
    Returns:
        导出的图片文件路径列表
    """
    # 使用辅助函数创建 Session（带重试逻辑）
    session = create_photoshop_session(max_retries=5, retry_delay=2)
    
    with session:
        app = session.app
        doc = app.open(str(psd_path))
        
        # 查找所有智能对象
        all_smart_objects = find_smart_object_layers(doc, None, debug=False)
        
        if not all_smart_objects:
            print("\n⚠️ 第一次查找未找到智能对象，启用详细调试模式重新查找...\n")
            all_smart_objects = find_smart_object_layers(doc, None, debug=True)
        
        if not all_smart_objects:
            doc.close()
            raise ValueError("PSD 文件中没有找到任何智能对象图层")
        
        # ========== 打印 PSD 文件基本信息 ==========
        print("\n" + "=" * 70)
        print("📋 PSD 文件信息")
        print("=" * 70)
        print(f"文件路径: {psd_path}")
        print(f"文件大小: {psd_path.stat().st_size / 1024 / 1024:.2f} MB")
        print(f"文档名称: {doc.name}")
        print(f"文档尺寸: {int(doc.width)} x {int(doc.height)} 像素")
        print(f"分辨率: {int(doc.resolution)} DPI")
        print(f"智能图层总数: {len(all_smart_objects)}")
        print(f"配置数量: {len(smart_objects_config)}")
        print("=" * 70)
        
        # ========== 匹配配置和智能对象 ==========
        # 匹配策略：
        # 1. 如果配置指定了 smart_object_name，优先按名称模糊匹配（PS中的名字包含参数中的关键字即可）
        # 2. 如果名称无法匹配，再按顺序匹配
        # 3. 如果配置数量少于智能对象数量，复用配置
        
        matched_pairs = []  # [(smart_object, config), ...]
        used_config_indices = set()  # 已使用的配置索引
        used_smart_object_indices = set()  # 已使用的智能对象索引
        
        # 第一轮：按名称模糊匹配（包含关键字即可，不区分大小写）
        for config_idx, so_config in enumerate(smart_objects_config):
            if so_config.get('smart_object_name'):
                target_keyword = so_config['smart_object_name'].strip()
                matched = False
                for so_idx, so in enumerate(all_smart_objects):
                    if so_idx in used_smart_object_indices:
                        continue
                    # 模糊匹配：PS中的名字包含参数中的关键字（不区分大小写）
                    so_name = so['name']
                    if target_keyword.lower() in so_name.lower():
                        matched_pairs.append((so, so_config))
                        used_config_indices.add(config_idx)
                        used_smart_object_indices.add(so_idx)
                        print(f"✅ 匹配: 智能对象 '{so_name}' <-> 配置[{config_idx}] (关键字: '{target_keyword}')")
                        matched = True
                        break
                
                if not matched:
                    print(f"⚠️  警告: 配置[{config_idx}] 的关键字 '{target_keyword}' 未匹配到任何智能对象，将按顺序匹配")
        
        # 第二轮：按顺序匹配剩余的配置和智能对象
        config_idx = 0
        for so_idx, so in enumerate(all_smart_objects):
            if so_idx in used_smart_object_indices:
                continue
            
            # 找到下一个未使用的配置
            while config_idx < len(smart_objects_config) and config_idx in used_config_indices:
                config_idx += 1
            
            if config_idx < len(smart_objects_config):
                so_config = smart_objects_config[config_idx]
                matched_pairs.append((so, so_config))
                used_config_indices.add(config_idx)
                used_smart_object_indices.add(so_idx)
                # 检查配置是否指定了名称但未匹配到
                if so_config.get('smart_object_name'):
                    print(f"✅ 匹配: 智能对象 '{so['name']}' <-> 配置[{config_idx}] (按顺序，配置中的关键字 '{so_config['smart_object_name']}' 未匹配到)")
                else:
                    print(f"✅ 匹配: 智能对象 '{so['name']}' <-> 配置[{config_idx}] (按顺序)")
                config_idx += 1
            else:
                # 配置用完了，复用第一个配置
                if len(smart_objects_config) > 0:
                    so_config = smart_objects_config[0]
                    matched_pairs.append((so, so_config))
                    used_smart_object_indices.add(so_idx)
                    print(f"✅ 匹配: 智能对象 '{so['name']}' <-> 配置[0] (复用)")
        
        if not matched_pairs:
            doc.close()
            raise ValueError("未能匹配任何智能对象和配置")
        
        print(f"\n📊 匹配结果: 共匹配 {len(matched_pairs)} 个智能对象")
        
        # ========== 打印智能对象详细信息 ==========
        print("\n" + "=" * 70)
        print("🔗 智能对象处理计划")
        print("=" * 70)
        for i, (so, so_config) in enumerate(matched_pairs, 1):
            print(f"\n  [{i}/{len(matched_pairs)}] {so['name']}")
            print(f"      图层路径: {so['path']}")
            print(f"      图片路径: {so_config['image_path']}")
            print(f"      缩放模式: {so_config.get('resize_mode', 'contain')}")
            print(f"      分块尺寸: {so_config.get('tile_size', 512)}")
        print("=" * 70)
        
        # ========== 处理所有智能对象 ==========
        print("\n" + "=" * 70)
        print("🔄 开始处理")
        print("=" * 70)
        
        processed_count = 0
        for i, (so, so_config) in enumerate(matched_pairs, 1):
            print(f"\n⏳ [{i}/{len(matched_pairs)}] 正在替换智能对象: {so['name']}...")
            try:
                image_path = Path(so_config['image_path'])
                resize_mode = so_config.get('resize_mode', 'contain')
                tile_size = so_config.get('tile_size', 512)
                custom_options = so_config.get('custom_options')
                
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
                print(f"✅ [{i}/{len(matched_pairs)}] 智能对象 '{so['name']}' 已替换")
                processed_count += 1
                
                # 确保回到主文档（每个替换操作后）
                try:
                    time.sleep(0.3)
                    current_active = session.active_document
                    if current_active != doc:
                        doc.activeLayer = so['layer']
                        print(f"    ✅ 已确保回到主文档")
                except Exception as e:
                    print(f"    ⚠️ 警告: 检查主文档时出错: {e}")
                    
            except Exception as e:
                print(f"❌ [{i}/{len(matched_pairs)}] 处理智能对象 '{so['name']}' 时出错: {e}")
                import traceback
                traceback.print_exc()
                # 继续处理下一个智能对象
                continue
        
        print(f"\n✅ 处理完成: 成功处理 {processed_count}/{len(matched_pairs)} 个智能对象")
        
        # 确保活动文档是主文档
        try:
            time.sleep(0.3)
            current_active = session.active_document
            if current_active != doc:
                if matched_pairs:
                    doc.activeLayer = matched_pairs[0][0]['layer']
                    print(f"    ✅ 已激活主文档和目标图层")
        except Exception as e:
            print(f"    ⚠️ 警告: 检查活动文档时出错: {e}")
        
        # ========== 查找画板并导出 ==========
        # 参考 erpfile.py 的原理：直接使用 doc.layerSets 获取所有图层组（画板）
        print(f"\n" + "=" * 70)
        print("🎨 检查画板（使用 doc.layerSets 方法）")
        print("=" * 70)
        print(f"PSD 文件路径: {psd_path}")
        print(f"文档名称: {doc.name if hasattr(doc, 'name') else '未知'}")
        
        export_paths = []  # 存储所有导出路径
        
        # 方法1: 直接使用 doc.layerSets（参考 erpfile.py）
        layer_sets = []
        try:
            if hasattr(doc, 'layerSets'):
                layer_sets = list(doc.layerSets) if hasattr(doc.layerSets, '__iter__') else [doc.layerSets]
                print(f"✅ 使用 doc.layerSets 找到 {len(layer_sets)} 个图层组（画板）")
                for i, ls in enumerate(layer_sets, 1):
                    ls_name = ls.name if hasattr(ls, 'name') else "未知"
                    print(f"   图层组[{i}]: {ls_name}")
        except Exception as e:
            print(f"⚠️ 使用 doc.layerSets 失败: {e}")
            layer_sets = []
        
        # 方法2: 如果 layerSets 为空，尝试使用分析服务查找
        if not layer_sets:
            print(f"\n尝试使用分析服务查找画板...")
            artboards = find_artboard_layers(doc, psd_path=psd_path, debug=True)
            if artboards:
                # 将分析服务找到的画板转换为图层组列表
                layer_sets = [ab['layer'] for ab in artboards]
                print(f"✅ 通过分析服务找到 {len(layer_sets)} 个画板")
        
        # 如果有图层组（画板），逐个导出
        if layer_sets:
            print(f"\n🔒 强制验证: 找到 {len(layer_sets)} 个图层组（画板），必须导出 {len(layer_sets)} 个文件")
            print(f"   如果最终导出数量不匹配，将显示错误信息")
            print("=" * 70)
            
            # 保存所有图层组的可见性状态（用于后续恢复）
            original_visibility = {}
            try:
                for ls in layer_sets:
                    try:
                        ls_name = ls.name if hasattr(ls, 'name') else "未知"
                        original_visibility[ls_name] = ls.visible if hasattr(ls, 'visible') else True
                    except Exception:
                        continue
                print(f"    ✅ 已保存 {len(original_visibility)} 个图层组的可见性状态")
            except Exception as e:
                print(f"    ⚠️ 警告: 保存图层可见性时出错: {e}")
            
            # 强制循环：确保每个图层组都被处理（参考 erpfile.py，但去掉 break）
            print(f"\n🔄 开始循环处理 {len(layer_sets)} 个图层组（画板）...")
            print(f"   图层组列表:")
            for idx, ls in enumerate(layer_sets, 1):
                ls_name = ls.name if hasattr(ls, 'name') else "未知"
                print(f"     [{idx}] {ls_name}")
            print(f"   将逐个处理以上 {len(layer_sets)} 个图层组\n")
            
            for i, artboard_layer in enumerate(layer_sets, 1):
                # 获取图层组名称
                try:
                    artboard_name = artboard_layer.name if hasattr(artboard_layer, 'name') else f"图层组{i}"
                except Exception:
                    artboard_name = f"图层组{i}"
                
                print(f"\n" + "=" * 70)
                print(f"⏳ [{i}/{len(layer_sets)}] 正在导出图层组（画板）: {artboard_name}")
                print("=" * 70)
                print(f"🔍 循环验证: 这是第 {i} 个图层组，共 {len(layer_sets)} 个")
                print(f"   图层组名称: '{artboard_name}'")
                print(f"   图层对象: {type(artboard_layer).__name__}")
                
                # 强制确保每个图层组都有唯一的文件名（使用索引）
                try:
                    # 生成导出文件名（确保唯一性）
                    if output_filename is None:
                        base_name = psd_path.stem
                        # 清理图层组名称，移除特殊字符，避免文件名问题
                        safe_artboard_name = "".join(c for c in artboard_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_artboard_name = safe_artboard_name.replace(' ', '_')
                        # 使用索引确保文件名唯一，即使图层组名称相同
                        artboard_export_filename = f"{base_name}_artboard{i}_{safe_artboard_name}_export.png"
                    else:
                        # 如果指定了文件名，在文件名和扩展名之间插入图层组索引和名称
                        output_path = Path(output_filename)
                        safe_artboard_name = "".join(c for c in artboard_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_artboard_name = safe_artboard_name.replace(' ', '_')
                        # 使用索引确保唯一性
                        artboard_export_filename = f"{output_path.stem}_artboard{i}_{safe_artboard_name}{output_path.suffix}"
                    
                    artboard_export_path = export_dir / artboard_export_filename
                    print(f"    📝 导出文件名: {artboard_export_filename}")
                    print(f"    📁 完整路径: {artboard_export_path}")
                    print(f"    🔢 画板索引: {i}/{len(layer_sets)}")
                    
                    # 检查权限
                    has_permission, perm_error = check_write_permission(artboard_export_path)
                    if not has_permission:
                        print(f"    ❌ 权限检查失败: {perm_error}")
                        print(f"    ⚠️ 跳过图层组 [{i}/{len(layer_sets)}]: {artboard_name}")
                        export_paths.append(None)  # 占位，表示这个图层组导出失败
                        continue
                    print(f"    ✅ 权限检查通过")
                    
                    # 确保导出目录存在
                    artboard_export_path.parent.mkdir(parents=True, exist_ok=True)
                    print(f"    ✅ 导出目录已准备")
                    
                    # 参考 erpfile.py 的原理：先隐藏所有图层组，然后只显示当前图层组
                    try:
                        print(f"    🔄 正在设置图层可见性（参考 erpfile.py 原理）...")
                        print(f"       目标图层组名称: '{artboard_name}'")
                        
                        # 先隐藏所有图层组
                        print(f"       步骤1: 隐藏所有图层组...")
                        for ls in layer_sets:
                            try:
                                ls_name = ls.name if hasattr(ls, 'name') else "未知"
                                if hasattr(ls, 'visible'):
                                    ls.visible = False
                                    print(f"           🔒 隐藏: '{ls_name}'")
                            except Exception as e:
                                print(f"           ⚠️ 隐藏图层组时出错: {e}")
                        
                        # 只显示当前图层组
                        print(f"       步骤2: 只显示当前图层组 '{artboard_name}'...")
                        artboard_layer.visible = True
                        print(f"           ✅ 显示: '{artboard_name}'")
                        
                        # 验证可见性
                        print(f"       步骤3: 验证可见性...")
                        visible_count = 0
                        visible_names = []
                        for ls in layer_sets:
                            try:
                                if hasattr(ls, 'visible') and ls.visible:
                                    visible_count += 1
                                    ls_name = ls.name if hasattr(ls, 'name') else "未知"
                                    visible_names.append(ls_name)
                            except Exception:
                                pass
                        
                        print(f"           可见图层组数量: {visible_count}")
                        print(f"           可见图层组: {visible_names}")
                        
                        if visible_count == 1 and visible_names[0] == artboard_name:
                            print(f"           ✅ 验证通过: 只有目标图层组 '{artboard_name}' 可见")
                        else:
                            print(f"           ⚠️ 警告: 可见性设置可能不正确")
                            print(f"              预期: 只有 '{artboard_name}' 可见")
                            print(f"              实际: {visible_names}")
                        
                        # 选中当前图层组
                        doc.activeLayer = artboard_layer
                        print(f"    ✅ 已选中图层组: {artboard_name}")
                        
                        # 等待一下，让 PS 完成可见性设置
                        time.sleep(1.5)  # 增加等待时间，确保可见性设置生效
                        
                    except Exception as e:
                        print(f"    ⚠️ 警告: 设置图层可见性时出错: {e}")
                        import traceback
                        traceback.print_exc()
                        # 继续尝试导出
                    
                    # 导出画板
                    print(f"    📤 正在导出到: {artboard_export_path}")
                    try:
                        options = session.ExportOptionsSaveForWeb()
                        
                        # 记录导出前的状态
                        print(f"       当前活动图层: {doc.activeLayer.name if hasattr(doc.activeLayer, 'name') else '未知'}")
                        print(f"       导出区域: 整个文档（已隐藏其他图层组，只显示当前图层组）")
                        print(f"       导出文件: {artboard_export_filename}")
                        print(f"       导出目录: {export_dir}")
                        
                        # 重要：exportDocument 使用 SaveForWeb 时，需要传递目录路径，而不是完整文件路径
                        # 但我们需要指定文件名，所以先导出到临时文件，然后重命名
                        # 或者直接使用完整路径（某些版本可能支持）
                        # 参考 erpfile.py：传递目录路径，但文件名可能由 PS 自动生成
                        # 为了确保文件名正确，我们使用完整路径
                        export_file_path_str = str(artboard_export_path)
                        print(f"       导出路径（字符串）: {export_file_path_str}")
                        
                        # 导出文档（只包含当前可见的图层组）
                        # 注意：SaveForWeb 可能会自动添加扩展名，所以我们需要确保路径正确
                        doc.exportDocument(
                            export_file_path_str,
                            exportAs=session.ExportType.SaveForWeb,
                            options=options
                        )
                        print(f"    ✅ exportDocument 调用成功")
                        
                        # 等待文件写入完成
                        time.sleep(2.0)  # 增加等待时间，确保文件写入完成
                        
                        # 检查文件是否存在
                        # 注意：SaveForWeb 可能会修改文件名（添加扩展名或修改名称）
                        # Photoshop 会自动清理文件名中的特殊字符（空格、括号等）替换为 `-`
                        # 所以我们需要检查多种可能的文件名
                        max_retries = 10
                        retry_count = 0
                        actual_export_path = None
                        
                        # 生成文件名变体（Photoshop 可能会修改特殊字符）
                        # 将文件名中的空格、括号等特殊字符替换为 `-`（Photoshop 的行为）
                        sanitized_name = re.sub(r'[ ()\[\]]+', '-', artboard_export_filename)
                        sanitized_name = re.sub(r'-+', '-', sanitized_name)  # 多个 `-` 合并为一个
                        sanitized_name = sanitized_name.strip('-')  # 去掉首尾的 `-`
                        
                        # 可能的文件名变体
                        possible_paths = [
                            artboard_export_path,  # 原始路径
                            export_dir / sanitized_name,  # Photoshop 清理后的文件名
                            export_dir / f"{artboard_export_path.stem}.png",  # 可能去掉后缀
                            export_dir / artboard_export_filename,  # 原始文件名
                        ]
                        
                        # 如果原始路径没有 .png 扩展名，添加它
                        if not artboard_export_path.suffix.lower() == '.png':
                            possible_paths.append(export_dir / f"{artboard_export_path.stem}.png")
                        
                        print(f"       检查可能的文件路径:")
                        for pp in possible_paths:
                            print(f"          - {pp}")
                        
                        while retry_count < max_retries and actual_export_path is None:
                            for pp in possible_paths:
                                if pp.exists():
                                    actual_export_path = pp
                                    print(f"       找到文件: {actual_export_path}")
                                    break
                            
                            if actual_export_path is None:
                                retry_count += 1
                                time.sleep(0.5)
                                if retry_count < max_retries:
                                    print(f"       等待文件生成... ({retry_count}/{max_retries})")
                        
                        # 如果还是找不到，尝试在目录中搜索匹配的文件（基于时间戳和基本名称）
                        if actual_export_path is None:
                            print(f"       ⚠️ 未找到预期文件，尝试在目录中搜索匹配的文件...")
                            try:
                                # 提取时间戳部分（格式：_20251229_130113_085）
                                timestamp_match = re.search(r'_(\d{8}_\d{6}_\d{3})', artboard_export_filename)
                                if timestamp_match:
                                    timestamp = timestamp_match.group(1)
                                    # 搜索包含相同时间戳和画板标识的文件
                                    search_pattern = f"*{timestamp}*artboard*画板*.png"
                                    matching_files = list(export_dir.glob(search_pattern))
                                    if matching_files:
                                        # 按修改时间排序，取最新的
                                        matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                                        actual_export_path = matching_files[0]
                                        print(f"       找到匹配的文件: {actual_export_path}")
                            except Exception as search_error:
                                print(f"       搜索文件时出错: {search_error}")
                        
                        # 如果还是找不到，列出导出目录中的所有文件，帮助调试
                        if actual_export_path is None:
                            print(f"       ⚠️ 未找到预期文件，列出导出目录中的所有文件:")
                            try:
                                dir_files = list(export_dir.glob("*"))
                                if dir_files:
                                    # 只列出最近的文件（可能相关的）
                                    dir_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                                    for df in dir_files[:20]:  # 只显示最近20个文件
                                        print(f"          - {df.name} ({df.stat().st_size} 字节)")
                                else:
                                    print(f"          (目录为空)")
                            except Exception as e:
                                print(f"          (无法列出目录: {e})")
                        
                        if actual_export_path and actual_export_path.exists():
                            # 如果实际文件路径与预期不同，更新它
                            if actual_export_path != artboard_export_path:
                                print(f"       ⚠️ 注意: 实际文件路径与预期不同")
                                print(f"          预期: {artboard_export_path}")
                                print(f"          实际: {actual_export_path}")
                                artboard_export_path = actual_export_path
                            file_size = artboard_export_path.stat().st_size
                            file_size_mb = file_size / 1024 / 1024
                            print(f"    ✅✅✅ 导出成功! ✅✅✅")
                            print(f"       文件路径: {artboard_export_path}")
                            print(f"       文件大小: {file_size} 字节 ({file_size_mb:.2f} MB)")
                            print(f"       图层组 [{i}/{len(layer_sets)}]: {artboard_name}")
                            export_paths.append(artboard_export_path)
                            print(f"    ✅ 已添加到导出列表")
                            print(f"    📊 当前成功导出: {len([p for p in export_paths if p is not None])}/{len(layer_sets)} 个文件")
                        else:
                            print(f"    ❌❌❌ 错误: 导出文件不存在! ❌❌❌")
                            print(f"       预期路径: {artboard_export_path}")
                            print(f"       已重试 {max_retries} 次，文件仍未生成")
                            print(f"       图层组 [{i}/{len(layer_sets)}]: {artboard_name}")
                            print(f"       可能原因:")
                            print(f"         1. Photoshop 导出失败但未报错")
                            print(f"         2. 文件路径权限问题")
                            print(f"         3. 磁盘空间不足")
                            export_paths.append(None)  # 占位，表示这个图层组导出失败
                            
                    except Exception as export_error:
                        print(f"    ❌❌❌ exportDocument 调用失败: {export_error} ❌❌❌")
                        print(f"       图层组 [{i}/{len(layer_sets)}]: {artboard_name}")
                        import traceback
                        traceback.print_exc()
                        export_paths.append(None)  # 占位，表示这个图层组导出失败
                        continue
                        
                except Exception as e:
                    print(f"    ❌❌❌ 导出图层组 '{artboard_name}' 时发生异常: {e} ❌❌❌")
                    print(f"       图层组 [{i}/{len(layer_sets)}]: {artboard_name}")
                    import traceback
                    traceback.print_exc()
                    export_paths.append(None)  # 占位，表示这个图层组导出失败
                    continue
                
                # 循环结束标记
                print(f"\n    ✅ 图层组 [{i}/{len(layer_sets)}] 处理完成（无论成功或失败）")
                print(f"    📊 当前进度: 已处理 {i}/{len(layer_sets)} 个图层组")
                print(f"    📊 当前成功导出: {len([p for p in export_paths if p is not None])} 个文件")
            
            # 循环完成验证
            print(f"\n" + "=" * 70)
            print(f"🔄 循环处理完成验证")
            print("=" * 70)
            print(f"   预期处理图层组数: {len(layer_sets)}")
            print(f"   实际循环次数: {i} (应该等于 {len(layer_sets)})")
            print(f"   导出路径列表长度: {len(export_paths)} (应该等于 {len(layer_sets)})")
            if len(export_paths) != len(layer_sets):
                print(f"   ❌ 错误: 导出路径数量 ({len(export_paths)}) 不等于图层组数量 ({len(layer_sets)})")
            else:
                print(f"   ✅ 验证通过: 所有图层组都已处理")
            print("=" * 70)
            
            # 导出完成后，统计结果
            print(f"\n" + "=" * 70)
            print(f"📊 图层组导出统计")
            print("=" * 70)
            successful_exports = [p for p in export_paths if p is not None]
            failed_exports = len(export_paths) - len(successful_exports)
            print(f"   总图层组数: {len(layer_sets)}")
            print(f"   成功导出: {len(successful_exports)}")
            print(f"   失败数量: {failed_exports}")
            
            # 强制确保返回数量等于图层组数量
            if len(export_paths) != len(layer_sets):
                print(f"   ⚠️ 警告: 导出路径数量 ({len(export_paths)}) 不等于图层组数量 ({len(layer_sets)})")
                print(f"   正在修复: 补充占位符以确保数量一致...")
                # 补充 None 占位符，确保数量一致
                while len(export_paths) < len(layer_sets):
                    export_paths.append(None)
                    print(f"      补充了 1 个占位符，当前数量: {len(export_paths)}")
                # 如果多了，截断（理论上不应该发生）
                if len(export_paths) > len(layer_sets):
                    export_paths = export_paths[:len(layer_sets)]
                    print(f"      截断到 {len(layer_sets)} 个")
                print(f"   ✅ 修复完成: 现在返回 {len(export_paths)} 个路径（等于图层组数量）")
            
            # 重要：固定返回和分析出的画板一样数量的文件（包括失败的占位符）
            # 不筛选掉 None，保持所有路径（成功的是 Path 对象，失败的是 None）
            print(f"   📋 最终返回: {len(export_paths)} 个路径（成功: {len(successful_exports)}, 失败: {failed_exports}）")
            
            # 恢复所有图层组的可见性
            try:
                print(f"\n    🔄 正在恢复图层组可见性...")
                restored_count = 0
                for ls in layer_sets:
                    try:
                        ls_name = ls.name if hasattr(ls, 'name') else "未知"
                        if ls_name in original_visibility and hasattr(ls, 'visible'):
                            ls.visible = original_visibility[ls_name]
                            restored_count += 1
                    except Exception as e:
                        print(f"        ⚠️ 恢复图层组 '{ls_name}' 可见性时出错: {e}")
                        continue
                print(f"    ✅ 已恢复 {restored_count}/{len(layer_sets)} 个图层组的可见性")
            except Exception as e:
                print(f"    ⚠️ 警告: 恢复图层组可见性时出错: {e}")
        else:
            # 没有画板：按原来的逻辑导出一张图
            print("未找到画板，将导出整张文档")
            print("=" * 70)
            
            if output_filename is None:
                output_filename = f"{psd_path.stem}_export.png"
            
            export_path = export_dir / output_filename
            
            # 检查导出路径的权限
            print(f"\n⏳ 正在导出图片...")
            has_permission, perm_error = check_write_permission(export_path)
            if not has_permission:
                print(f"\n    ❌ 权限检查失败: {perm_error}")
                doc.close()
                raise PermissionError(f"导出路径没有写入权限: {perm_error}")
            
            print(f"    ✅ 权限检查通过")
            
            try:
                # 确保导出目录存在
                export_path.parent.mkdir(parents=True, exist_ok=True)
                
                options = session.ExportOptionsSaveForWeb()
                print(f"    导出路径: {export_path}")
                doc.exportDocument(
                    str(export_path),
                    exportAs=session.ExportType.SaveForWeb,
                    options=options
                )
                print(f"    ✅ 导出成功")
                export_paths.append(export_path)
            except Exception as e:
                print(f"\n❌ 导出失败: {e}")
                import traceback
                traceback.print_exc()
                doc.close()
                raise
        
        print(f"\n" + "=" * 70)
        print("✅ 最终处理结果")
        print("=" * 70)
        print(f"共导出 {len(export_paths)} 个文件:")
        if export_paths:
            for i, path in enumerate(export_paths, 1):
                if path and path.exists():
                    file_size_mb = path.stat().st_size / 1024 / 1024
                    print(f"  ✅ [{i}] {path.name} ({file_size_mb:.2f} MB)")
                    print(f"     完整路径: {path}")
                elif path:
                    print(f"  ❌ [{i}] {path.name} (文件不存在)")
                else:
                    print(f"  ❌ [{i}] (导出失败)")
        else:
            print(f"  ⚠️ 没有成功导出的文件!")
        print("=" * 70)
        
        # 最终验证：确保如果有图层组，返回数量一致
        if layer_sets:
            successful_count = len([p for p in export_paths if p is not None])
            if successful_count == 0:
                print(f"\n❌❌❌ 严重错误: 找到 {len(layer_sets)} 个图层组（画板），但没有任何文件成功导出! ❌❌❌")
                print(f"   请检查上方的错误日志，找出导出失败的原因")
            elif len(export_paths) != len(layer_sets):
                print(f"\n⚠️ 警告: 找到 {len(layer_sets)} 个图层组，但返回路径数量 ({len(export_paths)}) 不一致")
                print(f"   成功导出: {successful_count} 个文件")
                print(f"   请检查上方的错误日志")
            else:
                print(f"\n✅ 验证通过: 返回 {len(export_paths)} 个路径（等于图层组数量 {len(layer_sets)}）")
                print(f"   成功导出: {successful_count} 个文件")
        
        # 关闭主文档
        try:
            doc.close()
            print(f"主文档已关闭")
        except Exception as e:
            print(f"⚠️ 警告: 关闭主文档时出错: {e}")
    
    import gc
    gc.collect()
    # 统一返回列表格式，方便处理
    return export_paths if export_paths else []

