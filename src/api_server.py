"""
PSD 智能对象替换 API 服务
基于 FastAPI 提供 HTTP 接口
"""

import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator, model_validator
import uvicorn

# 添加项目路径
# PyInstaller 打包后的路径处理
if getattr(sys, 'frozen', False):
    # 打包后的可执行文件
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 临时目录
        project_root = Path(sys._MEIPASS)
    else:
        project_root = Path(sys.executable).parent
else:
    # 开发模式
    project_root = Path(__file__).parent.parent

sys.path.insert(0, str(project_root))

# 静态 UI 目录（优先 src/ui，其次根目录 ui）
STATIC_DIR_CANDIDATES = [
    project_root / "src" / "ui",
    project_root / "ui"
]
STATIC_DIR = next((p for p in STATIC_DIR_CANDIDATES if p.exists()), STATIC_DIR_CANDIDATES[0])

# 默认输出目录（与服务启动文件同级的 output 目录）
DEFAULT_EXPORT_DIR = project_root / "output"


def generate_unique_filename(original_filename: Optional[str], psd_path: Path) -> str:
    """
    生成带时间戳的唯一文件名，防止文件被覆盖
    
    Args:
        original_filename: 原始文件名（可选，如 None 则使用 PSD 文件名）
        psd_path: PSD 文件路径，用于生成默认文件名
    
    Returns:
        带时间戳的唯一文件名
    """
    # 生成时间戳（格式：YYYYMMDD_HHMMSS_毫秒，确保唯一性）
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 保留毫秒的前3位（微秒转毫秒）
    
    if original_filename:
        # 如果指定了文件名，在文件名和扩展名之间插入时间戳
        # 例如：result.png -> result_20241201_123456.png
        filename_path = Path(original_filename)
        stem = filename_path.stem
        suffix = filename_path.suffix or ".png"
        return f"{stem}_{timestamp}{suffix}"
    else:
        # 如果未指定文件名，使用 PSD 文件名 + 时间戳
        psd_stem = psd_path.stem
        return f"{psd_stem}_export_{timestamp}.png"

# 导入功能模块
try:
    from src.psd_img_replace_smartobject import process_psd_with_image, process_psd_with_image_multi
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import importlib.util
    module_path = Path(__file__).parent / "psd-img-replace-smartobject.py"
    spec = importlib.util.spec_from_file_location("psd_replace", module_path)
    psd_replace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(psd_replace)
    process_psd_with_image = psd_replace.process_psd_with_image
    process_psd_with_image_multi = psd_replace.process_psd_with_image_multi

# 导入 Photoshop 状态检测服务
try:
    from src.services import check_photoshop_status, analyze_psd
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import importlib.util
    service_path = Path(__file__).parent / "services" / "photoshop_status_service.py"
    spec = importlib.util.spec_from_file_location("ps_status", service_path)
    ps_status = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ps_status)
    check_photoshop_status = ps_status.check_photoshop_status
    
    # 导入 PSD 分析服务
    analysis_path = Path(__file__).parent / "services" / "psd_analysis_service.py"
    spec = importlib.util.spec_from_file_location("psd_analysis", analysis_path)
    psd_analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(psd_analysis)
    analyze_psd = psd_analysis.analyze_psd

# Photoshop 启动工具
try:
    from src.utils.photoshop_process import start_photoshop, close_photoshop_process, restart_photoshop, is_photoshop_running
except ImportError:
    import importlib.util
    helper_path = Path(__file__).parent / "utils" / "photoshop_process.py"
    spec = importlib.util.spec_from_file_location("ps_proc", helper_path)
    ps_proc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ps_proc)
    start_photoshop = ps_proc.start_photoshop
    close_photoshop_process = ps_proc.close_photoshop_process
    restart_photoshop = ps_proc.restart_photoshop
    is_photoshop_running = ps_proc.is_photoshop_running

# 创建 FastAPI 应用
app = FastAPI(
    title="PSD 智能对象替换服务",
    description="""
## PSD 智能对象替换 API 服务

提供 PSD 智能对象替换和导出功能的 HTTP API 接口。

### 主要功能

- ✅ 替换 PSD 中的智能对象图层
- ✅ 自动缩放图片适配智能对象尺寸
- ✅ 导出处理后的图片
- ✅ 详细的错误信息和日志

### 使用说明

1. 确保 Photoshop 已安装并可访问
2. 提供正确的文件路径（PSD、图片、导出目录）
3. 可选指定智能对象名称，不指定则替换第一个找到的

### 注意事项

- 建议以管理员权限运行服务，避免权限问题
- 由于 Photoshop 限制，不支持并发处理
    """,
    version="1.0.0",
    docs_url="/docs",  # Swagger UI 路径
    openapi_url="/openapi.json",  # OpenAPI JSON 路径
    # 自定义 Swagger UI 配置
    swagger_ui_parameters={
        "deepLinking": True,  # 启用深度链接
        "displayRequestDuration": True,  # 显示请求耗时
        "filter": True,  # 启用过滤器
        "tryItOutEnabled": True,  # 启用"试用"功能
        "requestSnippetsEnabled": True,  # 启用请求代码片段
        "defaultModelsExpandDepth": 2,  # 默认展开模型深度
        "defaultModelExpandDepth": 2,  # 默认展开模型深度
    }
)

# 挂载静态 UI（用于直接访问 Web 控制台）
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


# ========== 请求/响应模型 ==========

class Position(BaseModel):
    """位置配置"""
    x: float = Field(..., ge=0, description="x 坐标（相对于智能对象左上角）", example=100)
    y: float = Field(..., ge=0, description="y 坐标（相对于智能对象左上角）", example=50)
    unit: str = Field(
        "px",
        description="单位：'px'（像素）或 '%'（百分比）",
        example="px"
    )
    
    @validator('unit')
    def validate_unit(cls, v):
        """验证单位"""
        if v not in {'px', '%'}:
            raise ValueError(f"单位必须是 'px' 或 '%'，当前值: {v}")
        return v
    
    @validator('x', 'y')
    def validate_percentage_range(cls, v, values):
        """验证百分比范围"""
        if 'unit' in values and values['unit'] == '%' and (v < 0 or v > 100):
            raise ValueError(f"百分比值必须在 0-100 之间，当前值: {v}")
        return v


class Size(BaseModel):
    """尺寸配置"""
    width: float = Field(..., gt=0, description="宽度", example=800)
    height: float = Field(..., gt=0, description="高度", example=600)
    unit: str = Field(
        "px",
        description="单位：'px'（像素）或 '%'（百分比）",
        example="px"
    )
    maintain_aspect_ratio: bool = Field(
        False,
        description="是否保持宽高比（如果为 True，需要指定 aspect_ratio_base）",
        example=False
    )
    aspect_ratio_base: Optional[str] = Field(
        None,
        description="""
        宽高比基准（仅当 maintain_aspect_ratio=true 时使用）
        
        - "width"：以宽度为基准，高度自适应。如果计算出的高度超出智能对象，会裁剪超出部分
        - "height"：以高度为基准，宽度自适应。如果计算出的宽度超出智能对象，会裁剪超出部分
        
        当 maintain_aspect_ratio=false 时，此参数会被忽略
        """,
        example="width"
    )
    
    @validator('unit')
    def validate_unit(cls, v):
        """验证单位"""
        if v not in {'px', '%'}:
            raise ValueError(f"单位必须是 'px' 或 '%'，当前值: {v}")
        return v
    
    @validator('width', 'height')
    def validate_percentage_range(cls, v, values):
        """验证百分比范围"""
        if 'unit' in values and values['unit'] == '%' and (v < 0 or v > 100):
            raise ValueError(f"百分比值必须在 0-100 之间，当前值: {v}")
        return v
    
    @validator('aspect_ratio_base')
    def validate_aspect_ratio_base(cls, v, values):
        """验证宽高比基准"""
        maintain_aspect_ratio = values.get('maintain_aspect_ratio', False)
        if maintain_aspect_ratio:
            if v is None:
                raise ValueError("当 maintain_aspect_ratio=true 时，aspect_ratio_base 必须提供（'width' 或 'height'）")
            if v not in {'width', 'height'}:
                raise ValueError(f"aspect_ratio_base 必须是 'width' 或 'height'，当前值: {v}")
        return v


class CustomOptions(BaseModel):
    """自定义模式配置"""
    position: Position = Field(..., description="位置配置")
    size: Size = Field(..., description="尺寸配置")


class SmartObjectConfig(BaseModel):
    """单个智能对象的配置"""
    smart_object_name: Optional[str] = Field(
        None,
        description="智能对象图层名称（可选，不指定则按搜索顺序匹配）",
        example="图片"
    )
    image_path: str = Field(
        ...,
        description="素材图片路径（支持 JPG/PNG/BMP/TIFF 格式）",
        example=r"D:\images\image.jpg"
    )
    resize_mode: Optional[str] = Field(
        None,
        description="图片缩放模式（可选，未指定则使用 defaults.resize_mode）",
        example="custom"
    )
    custom_options: Optional[CustomOptions] = Field(
        None,
        description="自定义模式配置（仅当 resize_mode='custom' 时必需）",
        example=None
    )
    tile_size: Optional[int] = Field(
        None,
        ge=64,
        le=2048,
        description="图片缩放分块尺寸（可选，未指定则使用 defaults.tile_size）",
        example=512
    )
    
    @validator('image_path')
    def validate_image(cls, v):
        """验证图片文件路径格式（不检查文件是否存在，文件存在性检查在实际处理时进行）"""
        path = Path(v)
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"不支持的图片格式: {v}，支持的格式: {', '.join(valid_extensions)}")
        # 只验证格式，不检查文件是否存在
        # 返回原始路径字符串，让实际处理函数来处理路径解析
        return v
    
    @validator('resize_mode')
    def validate_resize_mode(cls, v):
        """验证缩放模式"""
        if v is None:
            return v
        valid_modes = {'stretch', 'contain', 'cover', 'custom'}
        if v not in valid_modes:
            raise ValueError(f"不支持的缩放模式: {v}，支持的模式: {', '.join(valid_modes)}")
        return v
    
    @model_validator(mode='after')
    def validate_custom_options(self):
        """验证自定义模式配置"""
        if self.resize_mode == 'custom':
            if self.custom_options is None:
                raise ValueError("当 resize_mode='custom' 时，custom_options 必须提供")
        return self


class DefaultOptions(BaseModel):
    """全局默认配置"""
    resize_mode: str = Field(
        "contain",
        description="默认图片缩放模式",
        example="contain"
    )
    custom_options: Optional[CustomOptions] = Field(
        None,
        description="默认自定义模式配置（仅当 resize_mode='custom' 时有效）",
        example=None
    )
    tile_size: int = Field(
        512,
        ge=64,
        le=2048,
        description="默认图片缩放分块尺寸",
        example=512
    )
    
    @validator('resize_mode')
    def validate_resize_mode(cls, v):
        """验证缩放模式"""
        valid_modes = {'stretch', 'contain', 'cover', 'custom'}
        if v not in valid_modes:
            raise ValueError(f"不支持的缩放模式: {v}，支持的模式: {', '.join(valid_modes)}")
        return v


class ProcessRequest(BaseModel):
    """处理请求模型（支持新旧两种格式）"""
    psd_path: str = Field(
        ...,
        description="PSD 套图文件路径",
        example=r"D:\templates\template.psd"
    )
    # ========== 新格式：支持多个智能对象 ==========
    smart_objects: Optional[list[SmartObjectConfig]] = Field(
        None,
        description="""
        智能对象配置数组（新格式，推荐使用）
        
        **使用说明**：
        - 如果提供了此字段，将使用新格式处理多个智能对象
        - 每个智能对象可以单独配置图片路径、缩放模式等参数
        - 如果数组只有一个配置，但 PSD 中有多个智能对象，会自动复用该配置
        - 如果数组配置数量少于智能对象数量，会循环复用配置
        
        **配置复用规则**：
        - 如果 smart_objects 数组只有 1 个配置，会复用给所有找到的智能对象
        - 如果 smart_objects 数组有多个配置，按顺序匹配智能对象
        - 如果某个智能对象指定了 smart_object_name，优先按名称匹配
        
        **示例**：
        ```json
        {
          "smart_objects": [
            {
              "smart_object_name": "左图",
              "image_path": "D:\\images\\left.png",
              "resize_mode": "custom",
              "custom_options": {...}
            },
            {
              "smart_object_name": "右图",
              "image_path": "D:\\images\\right.png",
              "resize_mode": "cover"
            }
          ]
        }
        ```
        """,
        example=None
    )
    defaults: Optional[DefaultOptions] = Field(
        None,
        description="""
        全局默认配置（仅当使用 smart_objects 时有效）
        
        **作用**：为 smart_objects 中的配置提供默认值
        
        **使用说明**：
        - 如果 smart_objects 中某个配置未指定 resize_mode，使用 defaults.resize_mode
        - 如果 smart_objects 中某个配置未指定 tile_size，使用 defaults.tile_size
        - 如果 smart_objects 中某个配置未指定 custom_options，使用 defaults.custom_options
        
        **示例**：
        ```json
        {
          "defaults": {
            "resize_mode": "contain",
            "tile_size": 512
          },
          "smart_objects": [
            {
              "image_path": "D:\\images\\img1.png"
              // resize_mode 和 tile_size 会使用 defaults 中的值
            }
          ]
        }
        ```
        """,
        example=None
    )
    # ========== 旧格式：向后兼容（单个智能对象） ==========
    image_path: Optional[str] = Field(
        None,
        description="""
        素材图片路径（旧格式，向后兼容）
        
        **注意**：如果提供了 smart_objects，此字段会被忽略
        如果未提供 smart_objects，则使用此字段（旧格式）
        """,
        example=r"D:\images\image.jpg"
    )
    export_dir: Optional[str] = Field(
        None,
        description="导出目录路径（可选，不指定则使用服务启动文件同级目录下的 output 目录）",
        example=r"D:\output"
    )
    smart_object_name: Optional[str] = Field(
        None,
        description="智能对象图层名称（可选，不指定则替换第一个找到的）",
        example="图片"
    )
    output_filename: Optional[str] = Field(
        None,
        description="导出文件名（可选，默认使用 PSD文件名_export.png）。注意：实际文件名会自动添加时间戳以确保唯一性，防止文件被覆盖",
        example="result.png"
    )
    tile_size: int = Field(
        512,
        ge=64,
        le=2048,
        description="""
        图片缩放分块尺寸（64-2048，默认512）
        
        **作用**：控制图片缩放时的分块处理大小，用于降低内存占用。
        
        **工作原理**：
        - 将大图片分成多个小块进行处理
        - 每个块的大小 = tile_size x tile_size 像素
        - 逐个处理每个块，处理完立即释放内存
        
        **推荐值**：
        - 512（默认）：适合大多数情况
        - 1024：适合中等大小图片（2000-5000像素）
        - 2048：适合超大图片（>5000像素）
        - 256：内存受限环境
        
        **性能影响**：
        - 较小值：内存占用更低，但处理时间稍长
        - 较大值：处理速度更快，但内存占用稍高
        """,
        example=512
    )
    resize_mode: str = Field(
        "contain",
        description="""
        图片缩放模式（默认 "contain"）
        
        **作用**：控制当素材图片与智能对象比例不一致时的处理方式。
        
        **可选值**：
        
        - **"stretch"**：拉伸填充模式
          - 不保持宽高比
          - 图片会被强制拉伸到智能对象的尺寸
          - ⚠️ **会变形**，可能导致图片看起来被压缩或拉伸
        
        - **"contain"**（推荐，默认）：完整显示模式
          - 保持图片宽高比
          - 完整显示整张图片
          - 如果比例不匹配，留白区域使用透明背景
          - ✅ **不会变形**，图片保持原始比例
          - 注意：透明背景会保存为 PNG 格式
        
        - **"cover"**：填充覆盖模式
          - 保持图片宽高比
          - 填充整个智能对象区域
          - 如果比例不匹配，会裁剪图片边缘部分
          - ✅ **不会变形**，但可能丢失部分内容
        
        - **"custom"**：自定义模式
          - 精确控制素材图在智能对象中的位置和尺寸
          - 支持像素（px）和百分比（%）单位
          - 可选择是否保持宽高比
          - 需要提供 `custom_options` 参数
          - 详见 `custom_options` 字段说明
        
        **使用建议**：
        - 大多数情况：使用 "contain"（默认），保证图片不变形
        - 需要填满区域且可以接受裁剪：使用 "cover"
        - 明确需要变形效果：使用 "stretch"（不推荐）
        - 需要精确控制位置和尺寸：使用 "custom"
        
        **示例场景**：
        - 智能对象 1000x1000，素材图 800x1200（竖图）
          - "contain": 图片完整显示，上下留白区域为透明背景
          - "cover": 图片填满，左右会被裁剪
          - "stretch": 图片被压缩成正方形（变形）
          - "custom": 根据 custom_options 精确控制位置和尺寸
        """,
        example="contain"
    )
    custom_options: Optional[CustomOptions] = Field(
        None,
        description="""
        自定义模式配置（仅当 resize_mode="custom" 时必需）
        
        **使用说明**：
        - 当 `resize_mode="custom"` 时，此参数必须提供
        - 当 `resize_mode` 为其他值时，此参数会被忽略
        
        **配置项**：
        
        - **position**：位置配置
          - `x`: x 坐标（相对于智能对象左上角）
          - `y`: y 坐标（相对于智能对象左上角）
          - `unit`: 单位，"px"（像素）或 "%"（百分比），默认 "px"
        
        - **size**：尺寸配置
          - `width`: 宽度
          - `height`: 高度
          - `unit`: 单位，"px"（像素）或 "%"（百分比），默认 "px"
          - `maintain_aspect_ratio`: 是否保持宽高比，默认 false
          - `aspect_ratio_base`: 宽高比基准（仅当 maintain_aspect_ratio=true 时必需）
            - "width"：以宽度为基准，高度自适应（如果超出智能对象会裁剪）
            - "height"：以高度为基准，宽度自适应（如果超出智能对象会裁剪）
        
        **示例**：
        ```json
        {
          "resize_mode": "custom",
          "custom_options": {
            "position": {
              "x": 100,
              "y": 50,
              "unit": "px"
            },
            "size": {
              "width": 800,
              "height": 600,
              "unit": "px",
              "maintain_aspect_ratio": false
            }
          }
        }
        ```
        
        **保持宽高比示例**：
        ```json
        {
          "resize_mode": "custom",
          "custom_options": {
            "position": {
              "x": 0,
              "y": 0,
              "unit": "px"
            },
            "size": {
              "width": 800,
              "height": 600,
              "unit": "px",
              "maintain_aspect_ratio": true,
              "aspect_ratio_base": "width"
            }
          }
        }
        ```
        """,
        example=None
    )
    verbose: bool = Field(
        True,
        description="""
        是否显示详细信息（默认True）
        
        **作用**：控制是否显示详细的处理过程日志。
        
        **verbose=true**（默认）：
        - 显示素材图信息（尺寸、格式、大小等）
        - 显示 PSD 文件信息（尺寸、分辨率、图层等）
        - 显示智能对象详细信息（名称、尺寸、位置等）
        - 显示处理过程的每个步骤
        - 显示验证信息
        
        **verbose=false**（静默模式）：
        - 只显示关键信息（开始、完成、错误）
        - 减少日志输出
        - 适合生产环境或批量处理
        
        **使用建议**：
        - 调试时：使用 true，便于排查问题
        - 生产环境：使用 false，减少日志干扰
        """,
        example=True
    )
    
    class Config:
        json_schema_extra = {
            "example":  {
                            "defaults": {
                            "resize_mode": "contain",
                            "tile_size": 512
                            },
                            "output_filename": "result.png",
                            "psd_path": "D:\\freepik\\双相框可用\\7484117.psd",
                            "smart_objects": [
                            {
                                "custom_options": {
                                "position": {
                                    "unit": "px",
                                    "x": 100,
                                    "y": 50
                                },
                                "size": {
                                    "height": 600,
                                    "maintain_aspect_ratio": False,
                                    "unit": "px",
                                    "width": 800
                                }
                                },
                                "image_path": "D:\\workspace\\yishe-ps\\examples\\re.jpg",
                                "resize_mode": "custom",
                                "smart_object_name": "左图",
                                "tile_size": 512
                            },
                            {
                                "image_path": "D:\\workspace\\yishe-ps\\examples\\sq.jpg",
                                "resize_mode": "cover",
                                "smart_object_name": "右图",
                                "tile_size": 1024
                            }
                            ],
                            "verbose": True
                        }
        }
    
    @validator('psd_path')
    def validate_psd_path_exists(cls, v):
        """验证 PSD 文件路径是否存在"""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"PSD 文件路径不存在: {v}")
        return str(path.absolute())
    
    @validator('image_path')
    def validate_image_path(cls, v):
        """验证图片文件路径（仅当使用旧格式时，v 不为 None）"""
        # 如果 v 为 None，说明使用新格式，跳过验证
        if v is None:
            return v
        path = Path(v)
        if not path.exists():
            raise ValueError(f"图片文件路径不存在: {v}")
        return str(path.absolute())
    
    @validator('export_dir')
    def validate_export_dir(cls, v):
        """验证导出目录（允许不存在，会自动创建）"""
        # 如果为 None，返回 None（将使用默认路径）
        if v is None:
            return None
        path = Path(v)
        # 检查是否是文件路径（不应该有扩展名）
        if path.suffix:
            raise ValueError(f"export_dir 必须是目录路径，不能是文件: {v}")
        # 如果目录不存在，尝试创建（检查父目录是否存在）
        if not path.exists():
            # 检查父目录是否存在
            parent = path.parent
            if parent != path and not parent.exists():
                raise ValueError(f"无法创建导出目录，父目录不存在: {v}")
            # 尝试创建目录以验证权限
            try:
                path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise ValueError(f"没有权限创建导出目录: {v}")
            except Exception as e:
                raise ValueError(f"无法创建导出目录: {v}, 错误: {e}")
        # 检查是否有写入权限
        if not os.access(path, os.W_OK):
            raise ValueError(f"导出目录没有写入权限: {v}")
        return str(path.absolute())
    
    @validator('psd_path')
    def validate_psd(cls, v):
        """验证 PSD 文件"""
        path = Path(v)
        if path.suffix.lower() != '.psd':
            raise ValueError(f"文件必须是 PSD 格式: {v}")
        return v
    
    @validator('image_path')
    def validate_image(cls, v):
        """验证图片文件"""
        path = Path(v)
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"不支持的图片格式: {v}，支持的格式: {', '.join(valid_extensions)}")
        return v
    
    @validator('resize_mode')
    def validate_resize_mode(cls, v):
        """验证缩放模式"""
        valid_modes = {'stretch', 'contain', 'cover', 'custom'}
        if v not in valid_modes:
            raise ValueError(f"不支持的缩放模式: {v}，支持的模式: {', '.join(valid_modes)}")
        return v
    
    @model_validator(mode='after')
    def validate_custom_options(self):
        """验证自定义模式配置"""
        if self.resize_mode == 'custom':
            if self.custom_options is None:
                raise ValueError("当 resize_mode='custom' 时，custom_options 必须提供")
        # 非 custom 模式时，custom_options 会被忽略，允许为 None 或提供
        
        return self
    
    @model_validator(mode='after')
    def validate_request_format(self):
        """验证请求格式：确保新旧格式的兼容性"""
        # 如果提供了 smart_objects，使用新格式
        if self.smart_objects is not None:
            if len(self.smart_objects) == 0:
                raise ValueError("smart_objects 数组不能为空，至少需要提供一个配置")
            # 新格式：确保 defaults 的 resize_mode 和 custom_options 匹配
            if self.defaults and self.defaults.resize_mode == 'custom':
                if self.defaults.custom_options is None:
                    raise ValueError("当 defaults.resize_mode='custom' 时，defaults.custom_options 必须提供")
            return self
        
        # 如果未提供 smart_objects，使用旧格式，必须提供 image_path
        if self.image_path is None:
            raise ValueError("必须提供 image_path（旧格式）或 smart_objects（新格式）之一")
        
        return self


class ProcessResponse(BaseModel):
    """处理响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[dict] = Field(None, description="响应数据")
    timestamp: str = Field(..., description="处理时间戳")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "处理成功",
                "data": {
                    "export_path": r"D:\output\result.png",
                    "export_file": "result.png",
                    "export_dir": r"D:\output",
                    "file_size": 1234567,
                    "file_size_mb": 1.18
                },
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    timestamp: str = Field(..., description="检查时间")


class PhotoshopStatusRequest(BaseModel):
    """Photoshop 状态检测请求模型"""
    test_connection: bool = Field(
        False,
        description="""
        是否测试 Photoshop COM 连接（默认 False）
        
        **作用**：控制是否进行实际的 COM 连接测试。
        
        **test_connection=false**（默认，快速模式）：
        - 只检查进程是否运行
        - 检查 COM 接口是否注册
        - 不进行实际连接测试
        - ⚡ **速度快**，适合频繁检查
        
        **test_connection=true**（完整模式）：
        - 执行所有基础检查
        - 额外进行实际的 COM 连接测试
        - 验证 Photoshop 是否真正可用
        - ⏱️ **速度较慢**（需要几秒），但更准确
        - 适合在开始处理前确认 PS 完全可用
        
        **使用建议**：
        - 日常监控：使用 false（快速）
        - 处理前检查：使用 true（确保可用）
        """,
        example=False
    )


class PhotoshopStatusResponse(BaseModel):
    """Photoshop 状态检测响应模型"""
    is_running: bool = Field(..., description="Photoshop 进程是否运行")
    is_available: bool = Field(..., description="Photoshop 是否可用（运行且可连接）")
    executable_path: Optional[str] = Field(None, description="Photoshop 可执行文件路径")
    com_registered: bool = Field(..., description="COM 接口是否注册")
    connection_test: Optional[dict] = Field(None, description="连接测试结果（如果 test_connection=true）")
    diagnostics: str = Field(..., description="诊断信息")
    timestamp: str = Field(..., description="检测时间戳")
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_running": True,
                "is_available": True,
                "executable_path": r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
                "com_registered": True,
                "connection_test": {
                    "success": True,
                    "error": None,
                    "version": "25.0.0"
                },
                "diagnostics": "✅ Photoshop 进程正在运行\n✅ Photoshop COM 接口已注册\n✅ 找到 Photoshop 可执行文件: C:\\Program Files\\Adobe\\Adobe Photoshop 2024\\Photoshop.exe",
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class SmartObjectInfo(BaseModel):
    """智能对象信息模型"""
    name: str = Field(..., description="智能对象名称")
    path: str = Field(..., description="智能对象完整路径（包含父图层）")
    visible: bool = Field(..., description="是否可见")
    opacity: float = Field(..., description="不透明度（0.0-1.0）")
    blend_mode: str = Field(..., description="混合模式")
    position: dict = Field(..., description="位置信息（x, y, left, top, right, bottom）")
    size: dict = Field(..., description="尺寸信息（width, height, aspect_ratio）")
    bounds: Optional[dict] = Field(None, description="边界框信息")
    smart_object: Optional[dict] = Field(None, description="智能对象特定信息")
    transform: Optional[dict] = Field(None, description="变换矩阵信息")
    has_effects: bool = Field(..., description="是否有图层效果")
    effects: Optional[list] = Field(None, description="图层效果列表")
    has_mask: bool = Field(..., description="是否有图层蒙版")
    mask: Optional[dict] = Field(None, description="图层蒙版信息")


class PSDAnalysisRequest(BaseModel):
    """PSD 分析请求模型"""
    psd_path: str = Field(
        ...,
        description="PSD 文件路径",
        example=r"D:\templates\template.psd"
    )
    
    @validator('psd_path')
    def validate_psd_path(cls, v):
        """验证 PSD 文件路径"""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"PSD 文件不存在: {v}")
        if path.suffix.lower() != '.psd':
            raise ValueError(f"文件必须是 PSD 格式: {v}")
        return str(path.absolute())


class PSDAnalysisResponse(BaseModel):
    """PSD 分析响应模型"""
    file_info: dict = Field(..., description="文件基本信息")
    document_info: dict = Field(..., description="文档信息（尺寸、分辨率等）")
    smart_objects: list = Field(..., description="智能对象列表（详细信息）")
    statistics: dict = Field(..., description="统计信息")
    timestamp: str = Field(..., description="分析时间戳")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_info": {
                    "file_path": r"D:\templates\template.psd",
                    "file_name": "template.psd",
                    "file_size": 12345678,
                    "file_size_mb": 11.78
                },
                "document_info": {
                    "width": 1920,
                    "height": 1080,
                    "color_mode": "RGB",
                    "depth": 8,
                    "channels": 3,
                    "resolution": {
                        "horizontal": 72.0,
                        "vertical": 72.0,
                        "unit": "pixels/inch"
                    }
                },
                "smart_objects": [
                    {
                        "name": "图片",
                        "path": "图片",
                        "visible": True,
                        "opacity": 1.0,
                        "blend_mode": "normal",
                        "position": {
                            "x": 100,
                            "y": 50,
                            "left": 100,
                            "top": 50,
                            "right": 900,
                            "bottom": 650
                        },
                        "size": {
                            "width": 800,
                            "height": 600,
                            "aspect_ratio": 1.3333
                        },
                        "bounds": {
                            "x1": 100,
                            "y1": 50,
                            "x2": 900,
                            "y2": 650
                        },
                        "smart_object": {
                            "unique_id": "12345",
                            "file_type": "embedded"
                        },
                        "has_effects": False,
                        "has_mask": False
                    }
                ],
                "statistics": {
                    "total_smart_objects": 1,
                    "total_layers": 5,
                    "has_smart_objects": True
                },
                "timestamp": "2024-01-01T12:00:00"
            }
        }


# ========== API 路由 ==========

@app.get("/", include_in_schema=False)
async def ui_index():
    """直接返回静态 UI 的入口页"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "UI 文件未找到",
        "expected": str(index_file),
        "tips": "确认 src/ui/index.html 是否存在"
    }


@app.get(
    "/service-info",
    tags=["基础"],
    summary="服务信息",
    description="获取服务基本信息和可用接口"
)
async def service_info():
    """
    服务信息 - 返回基本信息与主要接口路径
    """
    return {
        "service": "PSD 智能对象替换服务",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "ui": "/",
        "api": {
            "process": "/processPsd",
            "photoshopStatus": "/photoshopStatus",
            "analyzePsd": "/analyzePsd"
        }
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["基础"],
    summary="健康检查",
    description="检查服务运行状态，用于监控和负载均衡"
)
async def health_check():
    """
    健康检查接口
    
    返回服务状态、版本和时间戳，可用于：
    - 服务监控
    - 负载均衡健康检查
    - 服务可用性验证
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.post(
    "/processPsd",
    response_model=ProcessResponse,
    tags=["处理"],
    summary="处理 PSD 文件（支持单个或多个智能对象）",
    description="""
    替换 PSD 中的智能对象并导出图片。
    
    **支持两种格式**：
    
    ### 1. 旧格式（向后兼容）：单个智能对象
    使用 `image_path`、`resize_mode` 等字段，适用于单个智能对象的场景。
    
    ### 2. 新格式（推荐）：多个智能对象
    使用 `smart_objects` 数组，支持为每个智能对象单独配置参数。
    
    **处理流程**：
    1. 打开 PSD 文件
    2. 查找智能对象图层
    3. 匹配配置和智能对象（按名称或按顺序）
    4. 逐个处理每个智能对象：
       - 打开智能对象文档
       - 缩放素材图片适配智能对象尺寸
       - 替换智能对象内容
       - 保存并关闭智能对象文档
    5. 导出主文档为 PNG 图片
    
    **新格式配置复用规则**：
    - 如果 `smart_objects` 数组只有 1 个配置，会复用给所有找到的智能对象
    - 如果 `smart_objects` 数组有多个配置，按顺序匹配智能对象
    - 如果某个配置指定了 `smart_object_name`，优先按名称匹配
    - 如果配置数量少于智能对象数量，会循环复用配置
    
    **参数说明**：
    
    **新格式参数**（推荐）：
    - `smart_objects`: 智能对象配置数组（必需，当使用新格式时）
      - 每个配置包含：`smart_object_name`（可选）、`image_path`（必需）、`resize_mode`（可选）、`custom_options`（可选）、`tile_size`（可选）
    - `defaults`: 全局默认配置（可选）
      - 当 `smart_objects` 中某个配置未指定参数时，使用此默认值
    
    **旧格式参数**（向后兼容）：
    - `image_path`: 素材图片路径（必需，当使用旧格式时）
    - `resize_mode`: 图片缩放模式（可选，默认 "contain"）
    - `custom_options`: 自定义模式配置（可选）
    - `tile_size`: 图片缩放分块尺寸（可选，默认512）
    - `smart_object_name`: 智能对象图层名称（可选）
    
    **通用参数**：
    - `psd_path`: PSD 套图文件路径（必需）
    - `export_dir`: 导出目录路径（可选，不指定则使用服务启动文件同级目录下的 output 目录）
    - `output_filename`: 导出文件名（可选，默认使用 `PSD文件名_export.png`）。注意：实际文件名会自动添加时间戳以确保唯一性，防止文件被覆盖
    - `verbose`: 是否显示详细信息（可选，默认true）
    
    **返回数据**：
    - `export_path`: 导出文件的完整路径
    - `export_file`: 导出文件名
    - `export_dir`: 导出目录
    - `file_size`: 文件大小（字节）
    - `file_size_mb`: 文件大小（MB）
    
    **使用示例**：
    
    1. **旧格式**（单个智能对象）：
    ```json
    {
      "psd_path": "D:\\template.psd",
      "image_path": "D:\\image.jpg",
      "resize_mode": "contain"
    }
    ```
    
    2. **新格式**（多个智能对象，每个单独配置）：
    ```json
    {
      "psd_path": "D:\\template.psd",
      "smart_objects": [
        {
          "smart_object_name": "左图",
          "image_path": "D:\\left.jpg",
          "resize_mode": "custom",
          "custom_options": {...}
        },
        {
          "smart_object_name": "右图",
          "image_path": "D:\\right.jpg",
          "resize_mode": "cover"
        }
      ]
    }
    ```
    
    3. **新格式**（单个配置复用给所有智能对象）：
    ```json
    {
      "psd_path": "D:\\template.psd",
      "smart_objects": [
        {
          "image_path": "D:\\image.jpg",
          "resize_mode": "custom",
          "custom_options": {...}
        }
      ]
    }
    ```
    """,
    response_description="处理结果，包含导出文件路径和相关信息"
)
async def process_psd(request: ProcessRequest, response: Response):
    """
    处理 PSD 文件：替换智能对象并导出
    
    详细说明请查看上方的 description。
    """
    try:
        # 使用默认导出目录（如果未指定）
        export_dir = request.export_dir if request.export_dir else str(DEFAULT_EXPORT_DIR)
        
        # 确保默认目录存在
        default_path = Path(export_dir)
        if not default_path.exists():
            default_path.mkdir(parents=True, exist_ok=True)
        
        # 生成带时间戳的唯一文件名，防止文件被覆盖
        psd_path_obj = Path(request.psd_path)
        unique_filename = generate_unique_filename(request.output_filename, psd_path_obj)
        
        # 判断使用新格式还是旧格式
        if request.smart_objects is not None:
            # ========== 新格式：多个智能对象 ==========
            # 准备默认配置
            default_resize_mode = "contain"
            default_tile_size = 512
            default_custom_options = None
            
            if request.defaults:
                default_resize_mode = request.defaults.resize_mode
                default_tile_size = request.defaults.tile_size
                if request.defaults.custom_options:
                    default_custom_options = request.defaults.custom_options.dict()
            
            # 转换 smart_objects 配置为处理函数需要的格式
            smart_objects_config = []
            for so_config in request.smart_objects:
                so_dict = {
                    'smart_object_name': so_config.smart_object_name,
                    'image_path': so_config.image_path,
                    'resize_mode': so_config.resize_mode or default_resize_mode,
                    'tile_size': so_config.tile_size or default_tile_size,
                }
                # 处理 custom_options
                if so_config.resize_mode == 'custom' and so_config.custom_options:
                    so_dict['custom_options'] = so_config.custom_options.dict()
                elif so_dict['resize_mode'] == 'custom' and default_custom_options:
                    so_dict['custom_options'] = default_custom_options
                
                smart_objects_config.append(so_dict)
            
            # 构建配置
            config = {
                'export_dir': export_dir,
                'output_filename': unique_filename,
                'verbose': request.verbose,
                'smart_objects_config': smart_objects_config  # 新格式：传递配置数组
            }
            
            # 调用处理函数（新格式）
            export_path = process_psd_with_image_multi(
                psd_path=request.psd_path,
                config=config
            )
        else:
            # ========== 旧格式：单个智能对象（向后兼容） ==========
            # 构建配置
            config = {
                'export_dir': export_dir,
                'smart_object_name': request.smart_object_name,
                'output_filename': unique_filename,
                'tile_size': request.tile_size,
                'resize_mode': request.resize_mode,
                'verbose': request.verbose
            }
            
            # 如果使用自定义模式，添加 custom_options
            if request.resize_mode == 'custom' and request.custom_options:
                config['custom_options'] = request.custom_options.dict()
            
            # 调用处理函数（旧格式）
            export_path = process_psd_with_image(
                psd_path=request.psd_path,
                image_path=request.image_path,
                config=config
            )
        
        # 构建响应数据
        response_data = {
            'export_path': str(export_path),
            'export_file': export_path.name,
            'export_dir': str(export_path.parent),
            'file_size': export_path.stat().st_size if export_path.exists() else 0,
            'file_size_mb': round(export_path.stat().st_size / 1024 / 1024, 2) if export_path.exists() else 0
        }
        
        # 设置缓存控制头，避免 Swagger UI 显示旧结果
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return ProcessResponse(
            success=True,
            message="处理成功",
            data=response_data,
            timestamp=datetime.now().isoformat()
        )
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "文件不存在",
                "message": str(e),
                "suggestion": "请检查文件路径是否正确，确保文件存在"
            }
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "权限错误",
                "message": str(e),
                "suggestion": "请以管理员权限运行服务，或检查文件/目录的访问权限"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "参数错误",
                "message": str(e),
                "suggestion": "请检查请求参数是否符合要求"
            }
        )
    except Exception as e:
        import traceback
        error_detail = {
            "error": "处理失败",
            "message": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc() if request.verbose else None
        }
        raise HTTPException(status_code=500, detail=error_detail)


@app.get(
    "/photoshopStatus",
    response_model=PhotoshopStatusResponse,
    tags=["Photoshop"],
    summary="检测 Photoshop 状态",
    description="""
    检测 Photoshop 是否启动、可用，以及连接状态。
    
    **功能说明**：
    - 检查 Photoshop 进程是否运行
    - 检查 Photoshop 可执行文件是否存在
    - 检查 COM 接口是否注册
    - 可选：测试实际的 COM 连接（需要 test_connection=true）
    
    **使用场景**：
    - 在处理 PSD 文件前，先检查 Photoshop 是否可用
    - 监控 Photoshop 运行状态
    - 诊断 Photoshop 连接问题
    
    **参数说明**：
    - `test_connection`（可选，默认 false）：
      - false：快速检查，只检查进程和注册表
      - true：完整检查，包括实际连接测试（较慢但更准确）
    
    **返回信息**：
    - `is_running`: Photoshop 进程是否运行
    - `is_available`: Photoshop 是否可用（运行且可连接）
    - `executable_path`: Photoshop 可执行文件路径
    - `com_registered`: COM 接口是否注册
    - `connection_test`: 连接测试结果（如果 test_connection=true）
    - `diagnostics`: 详细的诊断信息
    
    **使用建议**：
    - 日常监控：使用默认参数（快速检查）
    - 处理前确认：使用 `?test_connection=true`（确保完全可用）
    """,
    response_description="Photoshop 状态信息，包含运行状态、可用性和诊断信息"
)
async def get_photoshop_status(test_connection: bool = False):
    """
    检测 Photoshop 状态和可用性
    
    详细说明请查看上方的 description。
    """
    try:
        # 调用状态检测服务
        status_result = check_photoshop_status(test_connection=test_connection)
        
        return PhotoshopStatusResponse(
            is_running=status_result["is_running"],
            is_available=status_result["is_available"],
            executable_path=status_result.get("executable_path"),
            com_registered=status_result["com_registered"],
            connection_test=status_result.get("connection_test"),
            diagnostics=status_result["diagnostics"],
            timestamp=status_result["timestamp"]
        )
        
    except Exception as e:
        import traceback
        error_detail = {
            "error": "检测 Photoshop 状态失败",
            "message": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        raise HTTPException(status_code=500, detail=error_detail)


@app.post(
    "/startPhotoshop",
    tags=["Photoshop"],
    summary="启动 Photoshop（如果未运行）",
    description="尝试启动 Photoshop，如果已运行则直接返回成功。"
)
async def start_photoshop_handler(timeout: int = 30):
    """
    启动 Photoshop：
    - 如果已经运行，直接返回成功
    - 如果未运行，尝试在 timeout 秒内启动
    """
    try:
        ok = start_photoshop(timeout=timeout)
        if not ok:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "启动失败",
                    "message": "未能在指定时间内启动 Photoshop，请确认安装路径或手动启动。"
                }
            )
        return {
            "success": True,
            "message": "Photoshop 已运行或启动成功",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": "启动 Photoshop 失败",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
        )


@app.post(
    "/stopPhotoshop",
    tags=["Photoshop"],
    summary="关闭 Photoshop",
    description="关闭正在运行的 Photoshop 进程。"
)
async def stop_photoshop_handler(force: bool = False):
    """
    关闭 Photoshop：
    - force=False：优雅关闭（terminate），等待进程正常退出
    - force=True：强制关闭（kill），立即终止进程
    """
    try:
        if not is_photoshop_running():
            return {
                "success": True,
                "message": "Photoshop 未运行",
                "timestamp": datetime.now().isoformat()
            }
        
        ok = close_photoshop_process(force=force)
        if not ok:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "关闭失败",
                    "message": "无法关闭 Photoshop 进程，请检查权限。"
                }
            )
        return {
            "success": True,
            "message": "Photoshop 已关闭",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": "关闭 Photoshop 失败",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
        )


@app.post(
    "/restartPhotoshop",
    tags=["Photoshop"],
    summary="重启 Photoshop",
    description="先关闭 Photoshop（如果正在运行），然后重新启动。"
)
async def restart_photoshop_handler(timeout: int = 30):
    """
    重启 Photoshop：
    - 先关闭正在运行的 Photoshop
    - 然后重新启动 Photoshop
    - 如果未运行，直接启动
    """
    try:
        ok = restart_photoshop(timeout=timeout)
        if not ok:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "重启失败",
                    "message": "未能在指定时间内重启 Photoshop，请确认安装路径或手动启动。"
                }
            )
        return {
            "success": True,
            "message": "Photoshop 重启成功",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": "重启 Photoshop 失败",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
        )


@app.post(
    "/analyzePsd",
    response_model=PSDAnalysisResponse,
    tags=["PSD 分析"],
    summary="分析 PSD 文件",
    description="""
    分析 PSD 文件，提取整体信息和智能对象详细信息。
    
    **功能说明**：
    - 提取 PSD 文件的整体尺寸、分辨率、颜色模式等信息
    - 查找并分析所有智能对象图层
    - 提取每个智能对象的详细信息：
      - 名称和路径
      - 位置（x, y, left, top, right, bottom）
      - 尺寸（width, height, aspect_ratio）
      - 边界框信息
      - 智能对象特定信息（unique_id, file_type等）
      - 变换矩阵信息
      - 图层效果和蒙版信息
    
    **使用场景**：
    - 在处理 PSD 文件前，先了解文件结构和智能对象信息
    - 获取智能对象的精确位置和尺寸，用于后续处理
    - 验证 PSD 文件是否包含智能对象
    - 分析 PSD 文件结构
    
    **技术说明**：
    - 使用 `psd-tools` 库进行解析（不需要 Photoshop 运行）
    - 跨平台支持（Windows、Mac、Linux）
    - 快速解析，无需启动 Photoshop
    
    **返回信息**：
    - `file_info`: 文件基本信息（路径、名称、大小）
    - `document_info`: 文档信息（宽度、高度、分辨率、颜色模式等）
    - `smart_objects`: 智能对象列表，每个包含详细信息
    - `statistics`: 统计信息（智能对象数量、图层总数等）
    
    **注意事项**：
    - 此接口不需要 Photoshop 运行
    - 如果 PSD 文件损坏或格式不正确，会返回错误
    - 某些复杂的智能对象信息可能无法完全提取
    """,
    response_description="PSD 文件分析结果，包含文档信息和智能对象详细信息"
)
async def analyze_psd_file(request: PSDAnalysisRequest):
    """
    分析 PSD 文件
    
    详细说明请查看上方的 description。
    """
    try:
        # 调用分析服务
        analysis_result = analyze_psd(request.psd_path)
        
        return PSDAnalysisResponse(
            file_info=analysis_result["file_info"],
            document_info=analysis_result["document_info"],
            smart_objects=analysis_result["smart_objects"],
            statistics=analysis_result["statistics"],
            timestamp=analysis_result["timestamp"]
        )
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "文件不存在",
                "message": str(e),
                "suggestion": "请检查文件路径是否正确，确保文件存在"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "参数错误",
                "message": str(e),
                "suggestion": "请确保文件是 PSD 格式"
            }
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "依赖库未安装",
                "message": str(e),
                "suggestion": "请运行: pip install psd-tools"
            }
        )
    except Exception as e:
        import traceback
        error_detail = {
            "error": "分析 PSD 文件失败",
            "message": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        raise HTTPException(status_code=500, detail=error_detail)


# 注意：启动服务的入口文件已移动到项目根目录的 start_api_server.py
# 这里不再包含启动逻辑，只保留 API 定义

