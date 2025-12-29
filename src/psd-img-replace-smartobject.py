"""
PSD 智能对象替换脚本（重构版）
功能：找到 PSD 中的智能对象图层，替换为新图片，并导出到指定目录

此文件已重构，将功能拆分为多个模块：
- utils/permission_utils.py: 权限检查
- layer_finder.py: 图层查找（智能对象、画板）
- smart_object_replacer.py: 智能对象替换核心逻辑
"""

import gc
import sys
import os
import time
import io
import contextlib
from pathlib import Path
from typing import Optional, List

# 设置标准输出和错误输出为 UTF-8 编码，避免 Windows GBK 编码问题
if sys.platform == 'win32':
    # 重新配置标准输出和错误输出为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from photoshop import Session

# 导入工具模块
try:
    from .utils import create_photoshop_session, validate_job_inputs
    from .utils.permission_utils import check_write_permission, check_photoshop_permissions
    from .layer_finder import find_smart_object_layers, find_artboard_layers, debug_print_all_layers
    from .smart_object_replacer import replace_smart_object_content
    from .psd_exporter import replace_and_export_psd_multi
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.utils import create_photoshop_session, validate_job_inputs
    from src.utils.permission_utils import check_write_permission, check_photoshop_permissions
    from src.layer_finder import find_smart_object_layers, find_artboard_layers, debug_print_all_layers
    from src.smart_object_replacer import replace_smart_object_content
    from src.psd_exporter import replace_and_export_psd_multi


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
    
    # 使用辅助函数创建 Session（带重试逻辑）
    session = create_photoshop_session(max_retries=5, retry_delay=2)
    
    with session:
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
            time.sleep(0.3)
            
            # 如果智能对象文档还没关闭，确保回到主文档
            current_active = session.active_document
            if current_active != doc:
                print(f"    ⚠️ 警告: 活动文档不是主文档，尝试切换...")
                try:
                    # 尝试激活主文档
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


# 保留其他函数以保持向后兼容
# 这些函数会调用上面的 replace_and_export_psd
def process_psd_with_image(
    psd_path: str | Path,
    image_path: str | Path,
    config: dict | None = None
) -> Path:
    """
    封装函数：处理 PSD 套图，替换智能对象并导出
    
    详细文档请参考原文件
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
        'resize_mode': 'contain',
        'custom_options': None,
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


def process_psd_with_image_multi(
    psd_path: str | Path,
    config: dict | None = None
) -> List[Path]:
    """
    封装函数：处理 PSD 套图，支持多个智能对象的不同配置
    
    Args:
        psd_path: PSD 套图文件路径（字符串或 Path 对象）
        config: 配置字典，必需参数：
            - export_dir: 导出目录（必需）
            - smart_objects_config: 智能对象配置数组（必需）
                - 每个配置包含：
                    - smart_object_name: 智能对象图层名称（可选）
                    - image_path: 素材图片路径（必需）
                    - resize_mode: 图片缩放模式（可选，默认 "contain"）
                    - custom_options: 自定义模式配置（可选）
                    - tile_size: 图片缩放分块尺寸（可选，默认 512）
            - output_filename: 导出文件名（可选，默认使用 PSD 文件名_export.png）
            - verbose: 是否显示详细信息（可选，默认 True）
    
    Returns:
        导出的图片文件路径列表
    """
    # 转换路径类型
    psd_path = Path(psd_path)
    
    # 默认配置
    default_config = {
        'export_dir': None,  # 必需参数
        'smart_objects_config': None,  # 必需参数
        'output_filename': None,
        'verbose': True
    }
    
    # 合并配置
    if config is None:
        config = {}
    
    final_config = {**default_config, **config}
    
    # 验证必需参数
    if final_config['export_dir'] is None:
        raise ValueError("config['export_dir'] 是必需参数，请提供导出目录路径")
    
    if final_config['smart_objects_config'] is None or len(final_config['smart_objects_config']) == 0:
        raise ValueError("config['smart_objects_config'] 是必需参数，且不能为空，请提供至少一个智能对象配置")
    
    export_dir = Path(final_config['export_dir'])
    smart_objects_config = final_config['smart_objects_config']
    
    # 如果 verbose 为 False，临时禁用 print（通过重定向）
    if not final_config['verbose']:
        # 创建一个空的输出流来抑制打印
        null_stream = io.StringIO()
        with contextlib.redirect_stdout(null_stream), contextlib.redirect_stderr(null_stream):
            return replace_and_export_psd_multi(
                psd_path=psd_path,
                export_dir=export_dir,
                smart_objects_config=smart_objects_config,
                output_filename=final_config['output_filename']
            )
    else:
        return replace_and_export_psd_multi(
            psd_path=psd_path,
            export_dir=export_dir,
            smart_objects_config=smart_objects_config,
            output_filename=final_config['output_filename']
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

