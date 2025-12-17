# 使用 Windows Server Core 作为基础镜像
# 注意：这需要 Windows 容器支持（Windows Server 或 Windows 10/11 Pro/Enterprise）
FROM mcr.microsoft.com/windows/servercore:ltsc2022

# 设置环境变量
ENV CHOCOLATEY_VERSION=2.2.2

# 安装 Chocolatey（Windows 包管理器）
RUN powershell -Command \
    Set-ExecutionPolicy Bypass -Scope Process -Force; \
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; \
    iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1')); \
    choco feature enable -n allowGlobalConfirmation

# 安装 Python 3.11
RUN choco install python311 -y --params '/InstallDir:C:\Python311' && \
    refreshenv && \
    C:\Python311\python.exe -m pip install --upgrade pip

# 设置工作目录
WORKDIR C:\\app

# 复制 requirements.txt
COPY requirements.txt .

# 安装 Python 依赖
# 注意：photoshop 包需要 Windows COM，只能在 Windows 上安装
RUN C:\Python311\python.exe -m pip install --upgrade pip && \
    C:\Python311\python.exe -m pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY src/ ./src/
COPY examples/ ./examples/
COPY start_api_server.py .

# 创建输出目录
RUN if not exist output mkdir output

# 设置环境变量
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=1595

# 暴露端口
EXPOSE 1595

# 启动命令
# 注意：
# 1. 需要确保 Photoshop 已安装在容器中（C:\Program Files\Adobe\...）
# 2. 或者通过卷挂载主机的 Photoshop
# 3. 容器需要以交互模式运行以支持 GUI（如果 Photoshop 需要显示界面）
CMD ["C:\\Python311\\python.exe", "start_api_server.py"]

