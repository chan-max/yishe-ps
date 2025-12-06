# PSD 智能对象替换 API 服务使用文档

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

#### 方式1：使用启动脚本（推荐）

```bash
python start_api_server.py
```

#### 方式2：直接使用 uvicorn

```bash
uvicorn src.api_server:app --host 0.0.0.0 --port 1595
```

#### 方式3：开发模式（自动重载）

```bash
python start_api_server.py --reload
```

### 3. 访问 API 文档

启动服务后，访问：
- **Swagger UI**: http://localhost:1595/docs
- **ReDoc**: http://localhost:1595/redoc
- **健康检查**: http://localhost:1595/health

---

## API 接口说明

### 1. 健康检查

**GET** `/health`

检查服务状态

**响应示例**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00"
}
```

---

### 2. 处理单个 PSD 文件

**POST** `/api/v1/process`

替换 PSD 中的智能对象并导出图片

**请求体**:
```json
{
  "psd_path": "D:/templates/template.psd",
  "image_path": "D:/images/image.jpg",
  "export_dir": "D:/output",
  "smart_object_name": "图片",
  "output_filename": "result.png",
  "tile_size": 512,
  "verbose": true
}
```

**参数说明**:
- `psd_path` (必需): PSD 套图文件路径
- `image_path` (必需): 素材图片路径
- `export_dir` (必需): 导出目录路径
- `smart_object_name` (可选): 智能对象图层名称，不指定则替换第一个找到的
- `output_filename` (可选): 导出文件名，默认使用 `PSD文件名_export.png`
- `tile_size` (可选): 图片缩放分块尺寸，默认 512（范围: 64-2048）
- `verbose` (可选): 是否显示详细信息，默认 true

**响应示例**:
```json
{
  "success": true,
  "message": "处理成功",
  "data": {
    "export_path": "D:/output/result.png",
    "export_file": "result.png",
    "export_dir": "D:/output",
    "file_size": 1234567,
    "file_size_mb": 1.18
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

**错误响应**:
```json
{
  "detail": "文件不存在: D:/templates/template.psd"
}
```

---

### 3. 批量处理

**POST** `/api/v1/process/batch`

批量处理多个 PSD 文件（串行执行）

**请求体**:
```json
[
  {
    "psd_path": "D:/templates/template1.psd",
    "image_path": "D:/images/image1.jpg",
    "export_dir": "D:/output"
  },
  {
    "psd_path": "D:/templates/template2.psd",
    "image_path": "D:/images/image2.jpg",
    "export_dir": "D:/output"
  }
]
```

**响应示例**:
```json
{
  "success": true,
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {
      "index": 1,
      "success": true,
      "psd_path": "D:/templates/template1.psd",
      "export_path": "D:/output/template1_export.png",
      "message": "处理成功"
    },
    {
      "index": 2,
      "success": true,
      "psd_path": "D:/templates/template2.psd",
      "export_path": "D:/output/template2_export.png",
      "message": "处理成功"
    }
  ],
  "timestamp": "2024-01-01T12:00:00"
}
```

---

## 使用示例

### Python 示例

```python
import requests

# API 服务地址
api_url = "http://localhost:1595/api/v1/process"

# 请求数据
data = {
    "psd_path": "D:/templates/template.psd",
    "image_path": "D:/images/image.jpg",
    "export_dir": "D:/output",
    "smart_object_name": "图片",
    "output_filename": "result.png"
}

# 发送请求
response = requests.post(api_url, json=data)

# 处理响应
if response.status_code == 200:
    result = response.json()
    if result["success"]:
        print(f"✅ 处理成功: {result['data']['export_path']}")
    else:
        print(f"❌ 处理失败: {result['message']}")
else:
    print(f"❌ 请求失败: {response.status_code}")
    print(response.json())
```

### cURL 示例

```bash
curl -X POST "http://localhost:1595/api/v1/process" \
  -H "Content-Type: application/json" \
  -d '{
    "psd_path": "D:/templates/template.psd",
    "image_path": "D:/images/image.jpg",
    "export_dir": "D:/output"
  }'
```

### JavaScript 示例

```javascript
const response = await fetch('http://localhost:1595/api/v1/process', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    psd_path: 'D:/templates/template.psd',
    image_path: 'D:/images/image.jpg',
    export_dir: 'D:/output',
    smart_object_name: '图片'
  })
});

const result = await response.json();
if (result.success) {
  console.log('✅ 处理成功:', result.data.export_path);
} else {
  console.error('❌ 处理失败:', result.message);
}
```

---

## 注意事项

### 1. Photoshop 要求
- 确保 Photoshop 已安装
- 服务启动时会自动检测并启动 Photoshop（如果未运行）
- 建议以管理员权限运行服务，避免权限问题

### 2. 并发限制
- 由于 Photoshop 的限制，**不建议使用多进程模式**
- 批量处理会串行执行，避免同时操作 Photoshop
- 建议使用单进程模式（默认）

### 3. 文件路径
- 支持绝对路径和相对路径
- Windows 路径使用 `/` 或 `\\` 都可以
- 确保所有路径都有访问权限

### 4. 错误处理
- API 会返回详细的错误信息
- 文件不存在: 404 错误
- 权限错误: 403 错误
- 参数错误: 400 错误
- 处理错误: 500 错误

---

## 服务配置

### 修改默认端口

```bash
python start_api_server.py --port 1596
```

### 修改主机地址

```bash
python start_api_server.py --host 127.0.0.1
```

### 开发模式（自动重载）

```bash
python start_api_server.py --reload
```

---

## 故障排查

### 1. 服务无法启动
- 检查端口是否被占用: `netstat -ano | findstr :1595`
- 检查 Python 版本: 需要 Python 3.8+
- 检查依赖是否安装: `pip install -r requirements.txt`

### 2. 处理失败
- 检查 Photoshop 是否运行
- 检查文件路径是否正确
- 检查文件权限
- 查看服务日志获取详细错误信息

### 3. 权限问题
- 以管理员权限运行服务
- 检查导出目录的写入权限
- 检查 PSD 文件所在目录的读取权限

---

## 性能优化建议

1. **单进程模式**: 由于 Photoshop 限制，使用单进程
2. **批量处理**: 使用批量接口而不是多次调用单个接口
3. **文件路径**: 使用绝对路径，避免路径解析开销
4. **缓存**: 对于重复的 PSD 文件，可以考虑缓存处理结果

---

## 安全建议

1. **生产环境**: 不要将服务暴露到公网
2. **认证**: 考虑添加 API 密钥或 Token 认证
3. **限流**: 考虑添加请求限流，避免资源耗尽
4. **日志**: 记录所有请求和处理结果，便于审计

