## yishe-ps

基于 `photoshop-python-api` 的自动化生产服务脚手架。此仓库从 `ps_client` 项目中提炼了与 Photoshop 交互的核心能力，提供一套轻量的服务化基础和示例，便于快速二次开发。

### 快速开始

1. 创建虚拟环境并安装依赖：
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -U pip -r requirements.txt
   ```

2. **简单示例 - 连接 Photoshop 并打开 PSD：**
   ```
   python -m src.simple_example
   ```
   运行后会提示输入 PSD 文件路径，然后会显示文档的基本信息（尺寸、分辨率、图层等）。
   
   **自动启动功能**：如果 Photoshop 未运行，程序会自动启动 Photoshop（默认启用）。你也可以设置 `auto_start=False` 来禁用自动启动，此时需要手动启动 Photoshop。

3. **完整示例 - 替换智能对象并导出：**
   ```
   python -m src.example_usage --png "D:\素材\sample.png" --psd "D:\模板\template.psd" --output "D:\输出"
   ```
   需要准备：
   - 一份包含智能对象的 PSD 模板
   - 一张用于替换的 PNG/JPG 图片

### 目录结构

```
yishe-ps/
├── requirements.txt          # 项目依赖
├── src/
│   ├── __init__.py          # 包初始化，导出主要接口
│   ├── photoshop_service.py # Photoshop 核心操作函数（智能对象替换、导出等）
│   ├── simple_example.py    # 简单的连接和打开 PSD 示例
│   ├── example_usage.py     # 完整的套图流程示例
│   └── utils/               # 通用工具函数模块
│       ├── __init__.py
│       ├── photoshop_process.py  # Photoshop 进程管理（启动、关闭、检测）
│       ├── image_utils.py        # 图像处理工具（分块缩放等）
│       └── file_utils.py         # 文件路径验证工具
└── readme.md
```

**模块说明：**
- `photoshop_service.py`：核心业务逻辑，处理 Photoshop 文档操作
- `utils/photoshop_process.py`：进程管理相关（自动启动、关闭 Photoshop）
- `utils/image_utils.py`：图像处理工具（分块缩放等通用方法）
- `utils/file_utils.py`：文件路径验证和目录创建

### 功能特性

- ✅ **自动启动 Photoshop**：如果 Photoshop 未运行，程序会自动启动（Windows 系统）
- ✅ **智能查找 Photoshop 路径**：自动从常见安装路径和注册表查找 Photoshop
- ✅ **函数式设计**：所有功能都是独立函数，无需类实例化
- ✅ **资源管理**：自动处理 Photoshop 会话和内存清理

### 后续扩展建议

- 在 `example_usage.py` 基础上挂载 HTTP 框架（FastAPI、Flask）以实现服务化接口。
- 引入配置中心或 `.env` 管理路径、OSS 参数等。
- 结合队列/调度系统（Celery、RQ）实现批量套图任务。