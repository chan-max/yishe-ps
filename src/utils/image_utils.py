"""图像处理相关的工具函数。"""

from PIL import Image
from enum import Enum
from typing import Literal, Optional


class ResizeMode(str, Enum):
    """图片缩放模式枚举"""
    STRETCH = "stretch"  # 拉伸填充（会变形）
    CONTAIN = "contain"  # 保持宽高比，完整显示（可能有留白）
    COVER = "cover"  # 保持宽高比，填充目标区域（可能裁剪）
    CUSTOM = "custom"  # 自定义模式，精确控制位置和尺寸


def resize_image_in_tiles(
    img: Image.Image, 
    target_size: tuple[int, int], 
    tile_size: int,
    mode: Literal["stretch", "contain", "cover", "custom"] = "stretch",
    background_color: tuple[int, ...] = (255, 255, 255),
    custom_options: Optional[dict] = None
) -> Image.Image:
    """分块缩放大尺寸图片，降低内存占用。
    
    参考 ps_client 中的实现，通过分块处理避免大图片一次性加载到内存。
    
    Args:
        img: 原始图像对象
        target_size: 目标尺寸 (width, height)，对于 custom 模式，这是智能对象的尺寸
        tile_size: 每个块的尺寸，默认值取决于调用方
        mode: 缩放模式
            - "stretch": 拉伸填充，不保持宽高比（会变形）
            - "contain": 保持宽高比，完整显示图片（留白区域使用透明背景）
            - "cover": 保持宽高比，填充目标区域（可能裁剪）
            - "custom": 自定义模式，精确控制位置和尺寸（需要 custom_options）
        background_color: 背景色参数（已废弃，contain 模式使用透明背景）
        custom_options: 自定义模式配置（仅当 mode="custom" 时使用）
            - position: {x, y, unit} - 位置配置
            - size: {width, height, unit, maintain_aspect_ratio} - 尺寸配置
        
    Returns:
        缩放后的图像对象
    """
    orig_width, orig_height = img.size
    target_width, target_height = target_size
    
    # 如果是 stretch 模式，使用原来的分块处理逻辑
    if mode == "stretch":
        scale_x = target_width / orig_width
        scale_y = target_height / orig_height
        
        resized_img = Image.new(img.mode, (target_width, target_height))
        for top in range(0, orig_height, tile_size):
            bottom = min(top + tile_size, orig_height)
            for left in range(0, orig_width, tile_size):
                right = min(left + tile_size, orig_width)
                box = (left, top, right, bottom)
                tile = img.crop(box)

                out_left = int(left * scale_x)
                out_top = int(top * scale_y)
                out_right = int(right * scale_x)
                out_bottom = int(bottom * scale_y)

                tile_resized = tile.resize((out_right - out_left, out_bottom - out_top), Image.LANCZOS)
                resized_img.paste(tile_resized, (out_left, out_top))

                tile.close()
                del tile_resized
        return resized_img
    
    # contain 和 cover 模式：先整体缩放保持宽高比，然后创建目标画布
    if mode == "contain":
        # contain 模式：保持宽高比，完整显示，留白区域使用透明背景
        scale = min(target_width / orig_width, target_height / orig_height)
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        # 先缩放图片
        scaled_img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # 转换为 RGBA 模式以支持透明背景
        if scaled_img.mode != "RGBA":
            scaled_img = scaled_img.convert("RGBA")
        
        # 创建透明背景的目标图像（RGBA 模式）
        resized_img = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        # 居中粘贴（使用 RGBA 图片的 alpha 通道作为遮罩）
        offset_x = (target_width - new_width) // 2
        offset_y = (target_height - new_height) // 2
        resized_img.paste(scaled_img, (offset_x, offset_y), scaled_img)
        scaled_img.close()
        return resized_img
    
    elif mode == "cover":
        # cover 模式：保持宽高比，填充目标区域（可能裁剪）
        scale = max(target_width / orig_width, target_height / orig_height)
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        # 先缩放图片
        scaled_img = img.resize((new_width, new_height), Image.LANCZOS)
        # 居中裁剪到目标尺寸
        offset_x = (new_width - target_width) // 2
        offset_y = (new_height - target_height) // 2
        resized_img = scaled_img.crop((offset_x, offset_y, offset_x + target_width, offset_y + target_height))
        scaled_img.close()
        return resized_img
    
    elif mode == "custom":
        # custom 模式：根据 custom_options 精确控制位置和尺寸
        if custom_options is None:
            raise ValueError("custom 模式需要提供 custom_options 参数")
        
        # 解析配置
        position = custom_options.get('position', {})
        size = custom_options.get('size', {})
        
        # 计算实际位置（像素）
        pos_x = position.get('x', 0)
        pos_y = position.get('y', 0)
        pos_unit = position.get('unit', 'px')
        if pos_unit == '%':
            pos_x = int(target_width * pos_x / 100)
            pos_y = int(target_height * pos_y / 100)
        else:
            pos_x = int(pos_x)
            pos_y = int(pos_y)
        
        # 计算实际尺寸（像素）
        size_width = size.get('width', target_width)
        size_height = size.get('height', target_height)
        size_unit = size.get('unit', 'px')
        maintain_aspect_ratio = size.get('maintain_aspect_ratio', False)
        aspect_ratio_base = size.get('aspect_ratio_base', 'width')
        
        if size_unit == '%':
            size_width = int(target_width * size_width / 100)
            size_height = int(target_height * size_height / 100)
        else:
            size_width = int(size_width)
            size_height = int(size_height)
        
        # 如果保持宽高比，根据指定的基准计算另一个维度
        if maintain_aspect_ratio:
            aspect_ratio = orig_width / orig_height
            if aspect_ratio_base == 'width':
                # 以宽度为基准，高度自适应
                calculated_height = int(size_width / aspect_ratio)
                size_height = calculated_height
                # 如果高度超出智能对象，会裁剪（不需要特殊处理，粘贴时会自动裁剪）
            elif aspect_ratio_base == 'height':
                # 以高度为基准，宽度自适应
                calculated_width = int(size_height * aspect_ratio)
                size_width = calculated_width
                # 如果宽度超出智能对象，会裁剪（不需要特殊处理，粘贴时会自动裁剪）
            else:
                raise ValueError(f"不支持的 aspect_ratio_base: {aspect_ratio_base}，支持的值: 'width', 'height'")
        
        # 缩放图片到指定尺寸
        scaled_img = img.resize((size_width, size_height), Image.LANCZOS)
        
        # 转换为 RGBA 模式以支持透明背景
        if scaled_img.mode != "RGBA":
            scaled_img = scaled_img.convert("RGBA")
        
        # 创建透明背景的目标图像（RGBA 模式，使用智能对象的尺寸）
        resized_img = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        
        # 在指定位置粘贴图片（使用 RGBA 图片的 alpha 通道作为遮罩）
        resized_img.paste(scaled_img, (pos_x, pos_y), scaled_img)
        scaled_img.close()
        return resized_img
    
    else:
        raise ValueError(f"不支持的缩放模式: {mode}，支持的模式: stretch, contain, cover, custom")

