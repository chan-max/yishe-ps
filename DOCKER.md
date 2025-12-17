# Docker 部署指南

## 概述

`yishe-ps` 项目依赖 Windows COM 接口与 Photoshop 交互，因此只能使用 Windows 容器。

## 快速开始

### 一键构建和发布（开发者）

```powershell
# 构建并发布到 DockerHub
.\build.ps1 1.0.0 your-dockerhub-username
```

### 一键拉取和运行（使用者）

```powershell
# 从 DockerHub 拉取并运行
.\run.ps1 your-username/yishe-ps:latest
```

## 系统要求

### 必需条件
- **Windows Server 2016+** 或 **Windows 10/11 Pro/Enterprise**
- **Docker Desktop for Windows**（启用 Windows 容器）
- 至少 **4GB 可用内存**
- 至少 **10GB 可用磁盘空间**

### 切换到 Windows 容器

1. 打开 Docker Desktop
2. 右键点击系统托盘中的 Docker 图标
3. 选择 "Switch to Windows containers"
4. 或使用命令：
   ```powershell
   & $Env:ProgramFiles\Docker\Docker\DockerCli.exe -SwitchDaemon
   ```

## 构建镜像

### 方式1：使用构建脚本（推荐）

```powershell
.\build.ps1 [版本号] [DockerHub用户名]

# 示例
.\build.ps1 1.0.0 myusername
```

脚本会自动：
1. 检查 Docker 环境
2. 切换到 Windows 容器模式
3. 构建镜像
4. 测试镜像
5. 发布到 DockerHub（可选）

### 方式2：手动构建

```powershell
# 构建镜像
docker build -t your-username/yishe-ps:latest .

# 测试镜像
docker run --rm your-username/yishe-ps:latest python --version

# 发布到 DockerHub
docker login
docker push your-username/yishe-ps:latest
```

## 运行容器

### 方式1：使用运行脚本（推荐）

```powershell
.\run.ps1 your-username/yishe-ps:latest
```

脚本会自动：
1. 检查镜像是否存在
2. 清理旧容器
3. 创建输出目录
4. 启动容器

### 方式2：使用 Docker Compose

```powershell
# 编辑 docker-compose.yml，设置正确的镜像名称
docker-compose up -d
```

### 方式3：手动运行

```powershell
docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -v "${PWD}\output:C:\app\output" `
    -v "${PWD}\examples:C:\app\examples" `
    --restart unless-stopped `
    your-username/yishe-ps:latest
```

## Photoshop 安装

**重要**：容器中需要安装 Photoshop 才能使用完整功能。

### 方案1：在容器中安装（推荐用于生产）

1. 启动临时容器：
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

### 方案2：通过卷挂载（推荐用于开发）

```powershell
docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -v "C:\Program Files\Adobe:C:\Program Files\Adobe" `
    your-username/yishe-ps:latest
```

### 方案3：使用包含 Photoshop 的镜像

如果你已经构建了包含 Photoshop 的镜像：
```powershell
.\run.ps1 your-username/yishe-ps:with-photoshop
```

## 访问服务

启动容器后，可以通过以下地址访问：

- **API 文档**: http://localhost:1595/docs
- **Web UI**: http://localhost:1595/ui
- **健康检查**: http://localhost:1595/health

## 常用命令

### 查看日志
```powershell
# 实时查看
docker logs -f yishe-ps

# 查看最近100行
docker logs --tail 100 yishe-ps
```

### 进入容器
```powershell
docker exec -it yishe-ps cmd
```

### 停止容器
```powershell
docker stop yishe-ps
```

### 删除容器
```powershell
docker stop yishe-ps
docker rm yishe-ps
```

### 查看容器状态
```powershell
docker ps -a
docker inspect yishe-ps
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

## 发布到 DockerHub

### 1. 登录 DockerHub
```powershell
docker login
```

### 2. 构建并发布
```powershell
.\build.ps1 1.0.0 your-username
```

### 3. 验证
```powershell
docker pull your-username/yishe-ps:latest
.\run.ps1 your-username/yishe-ps:latest
```

## 故障排查

### 容器无法启动

1. **检查 Docker 是否运行**：
   ```powershell
   docker version
   ```

2. **检查容器模式**：
   ```powershell
   docker version --format '{{.Server.Os}}'
   ```
   应该显示 `windows`

3. **查看容器日志**：
   ```powershell
   docker logs yishe-ps
   ```

### Photoshop 无法使用

1. **检查 Photoshop 是否安装**：
   ```powershell
   docker exec yishe-ps dir "C:\Program Files\Adobe"
   ```

2. **检查 Photoshop 进程**：
   ```powershell
   docker exec yishe-ps tasklist | findstr Photoshop
   ```

3. **测试 Photoshop COM 接口**：
   ```powershell
   docker exec yishe-ps python -c "import comtypes.client; print('COM available')"
   ```

### 端口被占用

```powershell
# 查看端口占用
netstat -ano | findstr :1595

# 使用其他端口
docker run -d --name yishe-ps -p 1596:1595 your-username/yishe-ps:latest
```

### 构建失败

1. **检查网络连接**（需要下载基础镜像和依赖）
2. **检查磁盘空间**（Windows 容器镜像较大）
3. **查看详细错误**：
   ```powershell
   docker build --no-cache -t yishe-ps:test .
   ```

## 性能优化

### 使用多阶段构建（可选）

可以创建两个 Dockerfile：
- `Dockerfile` - 完整版本（包含所有依赖）
- `Dockerfile.slim` - 精简版本（仅运行时依赖）

### 镜像大小优化

- 使用 `.dockerignore` 排除不必要的文件
- 清理 Chocolatey 缓存
- 使用更小的基础镜像（如果可能）

## 安全建议

1. **不要将 Photoshop 授权信息打包到镜像中**
2. **使用环境变量传递敏感信息**
3. **定期更新基础镜像和依赖**
4. **限制容器资源使用**

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

### Q: 容器中的文件如何访问？
A: 使用卷挂载或通过 `docker cp` 命令：
```powershell
docker cp yishe-ps:C:\app\output\result.png ./
```

## 技术支持

如有问题，请查看：
- 快速开始指南: [README_DOCKER.md](README_DOCKER.md)
- 项目 README: [readme.md](readme.md)
