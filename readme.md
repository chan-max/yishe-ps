## yishe-ps

基于 `photoshop-python-api` 的自动化生产服务脚手架。此仓库从 `ps_client` 项目中提炼了与 Photoshop 交互的核心能力，提供一套轻量的服务化基础和示例，便于快速二次开发。

### 快速开始

1. 创建虚拟环境并安装依赖：
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -U pip -r requirements.txt
   ```
2. 准备素材：
   - 一份包含智能对象的 PSD 模板。
   - 一张用于替换的 PNG/JPG 图片。
3. 运行示例：
   ```
   python -m src.example_usage --png "D:\素材\sample.png" --psd "D:\模板\template.psd" --output "D:\输出"
   ```

### 目录结构

- `requirements.txt`：与 `ps_client` 中 Photoshop 相关部分保持一致的最小依赖集合。
- `src/photoshop_service.py`：封装 Session 生命周期、智能对象替换和导出逻辑。
- `src/example_usage.py`：展示如何以服务方式调用 `PhotoshopService`。

### 后续扩展建议

- 在 `example_usage.py` 基础上挂载 HTTP 框架（FastAPI、Flask）以实现服务化接口。
- 引入配置中心或 `.env` 管理路径、OSS 参数等。
- 结合队列/调度系统（Celery、RQ）实现批量套图任务。