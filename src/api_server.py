"""
PSD 智能对象替换 API 服务
基于 FastAPI 提供 HTTP 接口
"""

import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import uvicorn

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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
    from src.psd_img_replace_smartobject import process_psd_with_image
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import importlib.util
    module_path = Path(__file__).parent / "psd-img-replace-smartobject.py"
    spec = importlib.util.spec_from_file_location("psd_replace", module_path)
    psd_replace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(psd_replace)
    process_psd_with_image = psd_replace.process_psd_with_image

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
- ✅ 支持批量处理
- ✅ 详细的错误信息和日志

### 使用说明

1. 确保 Photoshop 已安装并可访问
2. 提供正确的文件路径（PSD、图片、导出目录）
3. 可选指定智能对象名称，不指定则替换第一个找到的

### 注意事项

- 建议以管理员权限运行服务，避免权限问题
- 由于 Photoshop 限制，不支持并发处理
- 批量处理会串行执行
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


# ========== 请求/响应模型 ==========

class ProcessRequest(BaseModel):
    """处理请求模型"""
    psd_path: str = Field(
        ...,
        description="PSD 套图文件路径",
        example=r"D:\templates\template.psd"
    )
    image_path: str = Field(
        ...,
        description="素材图片路径（支持 JPG/PNG/BMP/TIFF 格式）",
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
        
        **使用建议**：
        - 大多数情况：使用 "contain"（默认），保证图片不变形
        - 需要填满区域且可以接受裁剪：使用 "cover"
        - 明确需要变形效果：使用 "stretch"（不推荐）
        
        **示例场景**：
        - 智能对象 1000x1000，素材图 800x1200（竖图）
          - "contain": 图片完整显示，上下留白区域为透明背景
          - "cover": 图片填满，左右会被裁剪
          - "stretch": 图片被压缩成正方形（变形）
        """,
        example="contain"
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
            "example": {
                "psd_path": r"D:\freepik\鼠标垫单个\waterproof-desk-mat-mockup-top-view.psd",
                "image_path": r"D:\workspace\yishe-ps\examples\paint.jpg",
                "export_dir": None,
                "smart_object_name": None,
                "output_filename": "result.png",
                "tile_size": 512,
                "resize_mode": "contain",
                "verbose": True
            }
        }
    
    @validator('psd_path', 'image_path')
    def validate_paths(cls, v):
        """验证文件路径是否存在"""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"路径不存在: {v}")
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
        valid_modes = {'stretch', 'contain', 'cover'}
        if v not in valid_modes:
            raise ValueError(f"不支持的缩放模式: {v}，支持的模式: {', '.join(valid_modes)}")
        return v


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


# ========== API 路由 ==========

@app.get(
    "/",
    tags=["基础"],
    summary="服务信息",
    description="获取服务基本信息和可用接口"
)
async def root():
    """
    根路径 - 返回服务基本信息
    
    返回服务名称、版本和主要接口路径
    """
    return {
        "service": "PSD 智能对象替换服务",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api": {
            "process": "/api/v1/process",
            "batch": "/api/v1/process/batch"
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
    "/api/v1/process",
    response_model=ProcessResponse,
    tags=["处理"],
    summary="处理单个 PSD 文件",
    description="""
    替换 PSD 中的智能对象并导出图片。
    
    **处理流程**：
    1. 打开 PSD 文件
    2. 查找智能对象图层（如果指定了名称则查找匹配的，否则使用第一个找到的）
    3. 打开智能对象文档
    4. 缩放素材图片适配智能对象尺寸
    5. 替换智能对象内容
    6. 保存并关闭智能对象文档
    7. 导出主文档为 PNG 图片
    
    **参数说明**：
    - `psd_path`: PSD 套图文件路径（必需）
    - `image_path`: 素材图片路径（必需，支持 JPG/PNG/BMP/TIFF）
    - `export_dir`: 导出目录路径（可选，不指定则使用服务启动文件同级目录下的 output 目录）
    - `smart_object_name`: 智能对象图层名称（可选，不指定则替换第一个找到的）
    - `output_filename`: 导出文件名（可选，默认使用 `PSD文件名_export.png`）。注意：实际文件名会自动添加时间戳以确保唯一性，防止文件被覆盖
    - `tile_size`: 图片缩放分块尺寸（可选，64-2048，默认512，用于处理大图片）
    - `verbose`: 是否显示详细信息（可选，默认true）
    
    **返回数据**：
    - `export_path`: 导出文件的完整路径
    - `export_file`: 导出文件名
    - `export_dir`: 导出目录
    - `file_size`: 文件大小（字节）
    - `file_size_mb`: 文件大小（MB）
    """,
    response_description="处理结果，包含导出文件路径和相关信息"
)
async def process_psd(request: ProcessRequest):
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
        
        # 构建配置
        config = {
            'export_dir': export_dir,
            'smart_object_name': request.smart_object_name,
            'output_filename': unique_filename,
            'tile_size': request.tile_size,
            'resize_mode': request.resize_mode,
            'verbose': request.verbose
        }
        
        # 调用处理函数
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


@app.post(
    "/api/v1/process/batch",
    tags=["处理"],
    summary="批量处理多个 PSD 文件",
    description="""
    批量处理多个 PSD 文件，串行执行。
    
    **注意事项**：
    - 由于 Photoshop 的限制，批量处理会串行执行（一个接一个）
    - 每个请求的处理时间取决于 PSD 文件大小和图片尺寸
    - 建议设置较长的超时时间（如 10 分钟）
    
    **请求格式**：
    传入一个数组，每个元素是一个 `ProcessRequest` 对象。
    
    **返回数据**：
    - `total`: 总任务数
    - `succeeded`: 成功数量
    - `failed`: 失败数量
    - `results`: 每个任务的处理结果数组
    """,
    response_description="批量处理结果，包含每个任务的处理状态"
)
async def process_psd_batch(requests: list[ProcessRequest], background_tasks: BackgroundTasks):
    """
    批量处理多个 PSD 文件
    
    注意：由于 Photoshop 的限制，批量处理会串行执行
    """
    results = []
    
    for i, request in enumerate(requests, 1):
        try:
            # 使用默认导出目录（如果未指定）
            export_dir = request.export_dir if request.export_dir else str(DEFAULT_EXPORT_DIR)
            
            # 确保默认目录存在
            default_path = Path(export_dir)
            if not default_path.exists():
                default_path.mkdir(parents=True, exist_ok=True)
            
            # 生成带时间戳的唯一文件名
            psd_path_obj = Path(request.psd_path)
            unique_filename = generate_unique_filename(request.output_filename, psd_path_obj)
            
            config = {
                'export_dir': export_dir,
                'smart_object_name': request.smart_object_name,
                'output_filename': unique_filename,
                'tile_size': request.tile_size,
                'resize_mode': request.resize_mode,
                'verbose': request.verbose
            }
            
            export_path = process_psd_with_image(
                psd_path=request.psd_path,
                image_path=request.image_path,
                config=config
            )
            
            results.append({
                'index': i,
                'success': True,
                'psd_path': request.psd_path,
                'export_path': str(export_path),
                'message': '处理成功'
            })
            
        except Exception as e:
            results.append({
                'index': i,
                'success': False,
                'psd_path': request.psd_path,
                'error': str(e),
                'message': f'处理失败: {str(e)}'
            })
    
    return {
        'success': True,
        'total': len(requests),
        'succeeded': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'results': results,
        'timestamp': datetime.now().isoformat()
    }


# 注意：启动服务的入口文件已移动到项目根目录的 start_api_server.py
# 这里不再包含启动逻辑，只保留 API 定义

