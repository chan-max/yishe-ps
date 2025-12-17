# Docker 一键部署指南

## 快速开始

### 1. 构建并发布镜像（开发者）

```powershell
# 方式1: 使用构建脚本（推荐）
.\build.ps1 1.0.0 your-dockerhub-username

# 方式2: 手动构建
docker build -t your-username/yishe-ps:latest .
docker push your-username/yishe-ps:latest
```

### 2. 拉取并运行镜像（使用者）

```powershell
# 方式1: 使用运行脚本（推荐）
.\run.ps1 your-username/yishe-ps:latest

# 方式2: 手动运行
docker pull your-username/yishe-ps:latest
docker run -d --name yishe-ps -p 1595:1595 your-username/yishe-ps:latest
```

## 前置要求

### 系统要求
- Windows Server 2016+ 或 Windows 10/11 Pro/Enterprise
- Docker Desktop for Windows（启用 Windows 容器）
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

### Photoshop 安装

**重要**：容器中需要安装 Photoshop 才能使用完整功能。

#### 方式1：在容器中安装（推荐用于生产）

1. 启动容器：
   ```powershell
   docker run -it --name yishe-ps-temp your-username/yishe-ps:latest cmd
   ```

2. 在容器中安装 Photoshop：
   - 将 Photoshop 安装文件复制到容器
   - 或通过卷挂载安装文件
   - 在容器中运行安装程序

3. 提交为新镜像：
   ```powershell
   docker commit yishe-ps-temp your-username/yishe-ps:with-photoshop
   ```

#### 方式2：通过卷挂载（推荐用于开发）

```powershell
docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -v "C:\Program Files\Adobe:C:\Program Files\Adobe" `
    your-username/yishe-ps:latest
```

## 使用说明

### 启动服务

```powershell
# 使用脚本启动
.\run.ps1 your-username/yishe-ps:latest

# 或手动启动
docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -v "${PWD}\output:C:\app\output" `
    your-username/yishe-ps:latest
```

### 访问服务

- **API 文档**: http://localhost:1595/docs
- **Web UI**: http://localhost:1595/ui
- **健康检查**: http://localhost:1595/health

### 查看日志

```powershell
# 实时查看日志
docker logs -f yishe-ps

# 查看最近100行
docker logs --tail 100 yishe-ps
```

### 停止服务

```powershell
docker stop yishe-ps
```

### 删除容器

```powershell
docker stop yishe-ps
docker rm yishe-ps
```

## 环境变量

可以通过环境变量配置服务：

```powershell
docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -e HOST=0.0.0.0 `
    -e PORT=1595 `
    your-username/yishe-ps:latest
```

## 数据持久化

### 输出目录

```powershell
docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -v "D:\output:C:\app\output" `
    your-username/yishe-ps:latest
```

### 示例文件

```powershell
docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -v "D:\examples:C:\app\examples" `
    your-username/yishe-ps:latest
```

## 故障排查

### 容器无法启动

1. 检查 Docker 是否运行：
   ```powershell
   docker version
   ```

2. 检查是否在 Windows 容器模式：
   ```powershell
   docker version --format '{{.Server.Os}}'
   ```
   应该显示 `windows`

3. 查看容器日志：
   ```powershell
   docker logs yishe-ps
   ```

### Photoshop 无法使用

1. 检查 Photoshop 是否安装：
   ```powershell
   docker exec yishe-ps dir "C:\Program Files\Adobe"
   ```

2. 检查 Photoshop 进程：
   ```powershell
   docker exec yishe-ps tasklist | findstr Photoshop
   ```

### 端口被占用

```powershell
# 查看端口占用
netstat -ano | findstr :1595

# 使用其他端口
docker run -d --name yishe-ps -p 1596:1595 your-username/yishe-ps:latest
```

## 发布到 DockerHub

### 1. 登录 DockerHub

```powershell
docker login
```

### 2. 构建镜像

```powershell
.\build.ps1 1.0.0 your-username
```

### 3. 验证镜像

```powershell
docker images your-username/yishe-ps
```

### 4. 测试运行

```powershell
.\run.ps1 your-username/yishe-ps:latest
```

## 常见问题

### Q: 为什么需要 Windows 容器？
A: 因为项目依赖 Windows COM 接口与 Photoshop 交互，只能在 Windows 环境运行。

### Q: 容器中必须安装 Photoshop 吗？
A: 如果只需要 PSD 分析功能（/analyzePsd），不需要。如果需要处理功能（/processPsd），必须安装。

### Q: 如何更新镜像？
A: 重新构建并推送：
```powershell
.\build.ps1 1.0.1 your-username
docker pull your-username/yishe-ps:1.0.1
```

### Q: 可以运行多个实例吗？
A: 可以，但需要修改端口：
```powershell
docker run -d --name yishe-ps-2 -p 1596:1595 your-username/yishe-ps:latest
```

## 技术支持

如有问题，请查看：
- 项目 README: [readme.md](readme.md)
- Docker 详细文档: [DOCKER.md](DOCKER.md)
- GitHub Issues: [项目 Issues](https://github.com/your-repo/issues)

