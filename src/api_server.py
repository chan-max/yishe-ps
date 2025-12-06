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
    description="提供 PSD 智能对象替换和导出功能的 API 服务",
    version="1.0.0"
)


# ========== 请求/响应模型 ==========

class ProcessRequest(BaseModel):
    """处理请求模型"""
    psd_path: str = Field(..., description="PSD 套图文件路径")
    image_path: str = Field(..., description="素材图片路径")
    export_dir: str = Field(..., description="导出目录路径")
    smart_object_name: Optional[str] = Field(None, description="智能对象图层名称（可选，不指定则替换第一个找到的）")
    output_filename: Optional[str] = Field(None, description="导出文件名（可选，默认使用 PSD文件名_export.png）")
    tile_size: int = Field(512, ge=64, le=2048, description="图片缩放分块尺寸（64-2048，默认512）")
    verbose: bool = Field(True, description="是否显示详细信息（默认True）")
    
    @validator('psd_path', 'image_path', 'export_dir')
    def validate_paths(cls, v):
        """验证路径是否存在"""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"路径不存在: {v}")
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


class ProcessResponse(BaseModel):
    """处理响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[dict] = Field(None, description="响应数据")
    timestamp: str = Field(..., description="处理时间戳")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    timestamp: str = Field(..., description="检查时间")


# ========== API 路由 ==========

@app.get("/", tags=["基础"])
async def root():
    """根路径"""
    return {
        "service": "PSD 智能对象替换服务",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["基础"])
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/v1/process", response_model=ProcessResponse, tags=["处理"])
async def process_psd(request: ProcessRequest):
    """
    处理 PSD 文件：替换智能对象并导出
    
    - **psd_path**: PSD 套图文件路径
    - **image_path**: 素材图片路径
    - **export_dir**: 导出目录路径
    - **smart_object_name**: 可选，智能对象图层名称
    - **output_filename**: 可选，导出文件名
    - **tile_size**: 图片缩放分块尺寸（默认512）
    - **verbose**: 是否显示详细信息（默认True）
    
    返回导出的图片路径和相关信息
    """
    try:
        # 构建配置
        config = {
            'export_dir': request.export_dir,
            'smart_object_name': request.smart_object_name,
            'output_filename': request.output_filename,
            'tile_size': request.tile_size,
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
        raise HTTPException(status_code=404, detail=f"文件不存在: {str(e)}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"权限错误: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"参数错误: {str(e)}")
    except Exception as e:
        import traceback
        error_detail = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        raise HTTPException(status_code=500, detail=error_detail)


@app.post("/api/v1/process/batch", tags=["处理"])
async def process_psd_batch(requests: list[ProcessRequest], background_tasks: BackgroundTasks):
    """
    批量处理多个 PSD 文件
    
    注意：由于 Photoshop 的限制，批量处理会串行执行
    """
    results = []
    
    for i, request in enumerate(requests, 1):
        try:
            config = {
                'export_dir': request.export_dir,
                'smart_object_name': request.smart_object_name,
                'output_filename': request.output_filename or f"batch_{i}_{Path(request.psd_path).stem}_export.png",
                'tile_size': request.tile_size,
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

