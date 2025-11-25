"""图像处理相关的工具函数。"""

from PIL import Image


def resize_image_in_tiles(img: Image.Image, target_size: tuple[int, int], tile_size: int) -> Image.Image:
    """分块缩放大尺寸图片，降低内存占用。
    
    参考 ps_client 中的实现，通过分块处理避免大图片一次性加载到内存。
    
    Args:
        img: 原始图像对象
        target_size: 目标尺寸 (width, height)
        tile_size: 每个块的尺寸，默认值取决于调用方
        
    Returns:
        缩放后的图像对象
    """
    orig_width, orig_height = img.size
    target_width, target_height = target_size
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

