# Docker 命令构建指南

## 前置要求

1. **切换到 Windows 容器模式**
   ```powershell
   # 方式1: 在 Docker Desktop 中切换
   # 右键点击系统托盘 Docker 图标 -> Switch to Windows containers
   
   # 方式2: 使用命令行
   & $Env:ProgramFiles\Docker\Docker\DockerCli.exe -SwitchDaemon
   ```

2. **验证容器模式**
   ```powershell
   docker version --format '{{.Server.Os}}'
   # 应该输出: windows
   ```

## 基础构建命令

### 1. 构建镜像

```powershell
# 基础构建（使用默认标签 latest）
docker build -t yishe-ps:latest .

# 指定版本标签
docker build -t yishe-ps:1.0.0 .

# 同时指定多个标签
docker build -t yishe-ps:latest -t yishe-ps:1.0.0 .

# 指定 Dockerfile（如果有多个）
docker build -f Dockerfile -t yishe-ps:latest .
```

### 2. 构建并指定 DockerHub 用户名

```powershell
# 构建时指定完整的镜像名称
docker build -t your-username/yishe-ps:latest .

# 同时指定版本和 latest
docker build -t your-username/yishe-ps:1.0.0 -t your-username/yishe-ps:latest .
```

## 完整构建流程

### 步骤 1: 构建镜像

```powershell
# 在项目根目录执行
cd D:\workspace\yishe-ps

# 构建镜像
docker build -t your-username/yishe-ps:latest .
```

**构建过程说明**：
- 下载 Windows Server Core 基础镜像（首次构建需要较长时间）
- 安装 Chocolatey 包管理器
- 安装 Python 3.11
- 安装 Python 依赖包
- 复制项目文件
- 设置环境变量和启动命令

### 步骤 2: 验证镜像

```powershell
# 查看镜像列表
docker images your-username/yishe-ps

# 测试镜像（检查 Python 是否正常）
docker run --rm your-username/yishe-ps:latest python --version

# 测试镜像（检查依赖是否安装）
docker run --rm your-username/yishe-ps:latest pip list
```

### 步骤 3: 本地测试运行

```powershell
# 创建输出目录
mkdir output -ErrorAction SilentlyContinue

# 运行容器
docker run -d `
    --name yishe-ps-test `
    -p 1595:1595 `
    -v "${PWD}\output:C:\app\output" `
    your-username/yishe-ps:latest

# 查看日志
docker logs -f yishe-ps-test

# 测试访问
curl http://localhost:1595/health
```

### 步骤 4: 发布到 DockerHub

```powershell
# 登录 DockerHub
docker login

# 推送镜像
docker push your-username/yishe-ps:latest

# 推送指定版本
docker push your-username/yishe-ps:1.0.0
```

## 高级构建选项

### 不使用缓存构建

```powershell
# 完全重新构建，不使用缓存
docker build --no-cache -t yishe-ps:latest .
```

### 构建时传递构建参数

```powershell
# 如果 Dockerfile 中有 ARG，可以这样传递
docker build --build-arg PYTHON_VERSION=3.11 -t yishe-ps:latest .
```

### 查看构建过程

```powershell
# 显示详细的构建输出
docker build --progress=plain -t yishe-ps:latest .

# 或者使用默认输出（已包含详细信息）
docker build -t yishe-ps:latest .
```

### 构建并保存到文件

```powershell
# 构建镜像
docker build -t yishe-ps:latest .

# 保存镜像到文件
docker save yishe-ps:latest -o yishe-ps-latest.tar

# 从文件加载镜像（在其他机器上）
docker load -i yishe-ps-latest.tar
```

## 常用构建命令组合

### 一键构建和测试

```powershell
# 构建
docker build -t yishe-ps:latest .

# 测试
docker run --rm yishe-ps:latest python --version

# 如果测试通过，运行服务
docker run -d --name yishe-ps -p 1595:1595 yishe-ps:latest
```

### 构建、测试、发布流程

```powershell
# 1. 构建
docker build -t your-username/yishe-ps:1.0.0 -t your-username/yishe-ps:latest .

# 2. 测试
docker run --rm your-username/yishe-ps:latest python --version

# 3. 登录 DockerHub
docker login

# 4. 发布
docker push your-username/yishe-ps:1.0.0
docker push your-username/yishe-ps:latest
```

## 构建优化

### 使用 .dockerignore

确保 `.dockerignore` 文件存在，排除不必要的文件：

```
__pycache__/
*.pyc
.venv/
build/
dist/
*.spec
.git/
```

### 多阶段构建（如果需要）

如果将来需要优化镜像大小，可以使用多阶段构建：

```dockerfile
# 构建阶段
FROM mcr.microsoft.com/windows/servercore:ltsc2022 AS builder
# ... 安装依赖和构建

# 运行阶段
FROM mcr.microsoft.com/windows/servercore:ltsc2022
COPY --from=builder /app /app
# ...
```

## 故障排查

### 构建失败：无法下载基础镜像

```powershell
# 检查网络连接
ping mcr.microsoft.com

# 手动拉取基础镜像
docker pull mcr.microsoft.com/windows/servercore:ltsc2022
```

### 构建失败：Chocolatey 安装失败

```powershell
# 查看详细错误
docker build --progress=plain -t yishe-ps:latest . 2>&1 | Select-String -Pattern "error"

# 尝试不使用缓存重新构建
docker build --no-cache -t yishe-ps:latest .
```

### 构建失败：Python 安装失败

```powershell
# 检查 Chocolatey 是否安装成功
docker run --rm -it mcr.microsoft.com/windows/servercore:ltsc2022 powershell
# 在容器中测试: choco --version

# 如果失败，可能需要更新 Dockerfile 中的 Chocolatey 安装方式
```

### 构建时间过长

```powershell
# 使用构建缓存（默认启用）
# 如果修改了代码但依赖没变，会使用缓存加速构建

# 查看构建历史
docker history yishe-ps:latest
```

## 实际使用示例

### 示例 1: 开发环境构建

```powershell
# 在项目根目录
cd D:\workspace\yishe-ps

# 构建开发版本
docker build -t yishe-ps:dev .

# 运行并挂载源代码（用于开发）
docker run -d `
    --name yishe-ps-dev `
    -p 1595:1595 `
    -v "${PWD}\src:C:\app\src" `
    -v "${PWD}\output:C:\app\output" `
    yishe-ps:dev
```

### 示例 2: 生产环境构建和发布

```powershell
# 1. 构建生产版本
docker build -t mycompany/yishe-ps:1.0.0 -t mycompany/yishe-ps:latest .

# 2. 本地测试
docker run --rm mycompany/yishe-ps:latest python --version

# 3. 登录 DockerHub
docker login

# 4. 发布
docker push mycompany/yishe-ps:1.0.0
docker push mycompany/yishe-ps:latest

# 5. 验证（在其他机器上）
docker pull mycompany/yishe-ps:latest
docker run -d --name yishe-ps -p 1595:1595 mycompany/yishe-ps:latest
```

### 示例 3: 批量构建多个版本

```powershell
# 构建多个版本
$versions = @("1.0.0", "1.0.1", "latest")

foreach ($version in $versions) {
    Write-Host "构建版本: $version" -ForegroundColor Yellow
    docker build -t your-username/yishe-ps:$version .
}
```

## 命令速查表

| 操作 | 命令 |
|------|------|
| 构建镜像 | `docker build -t yishe-ps:latest .` |
| 查看镜像 | `docker images yishe-ps` |
| 测试镜像 | `docker run --rm yishe-ps:latest python --version` |
| 运行容器 | `docker run -d --name yishe-ps -p 1595:1595 yishe-ps:latest` |
| 查看日志 | `docker logs -f yishe-ps` |
| 登录 DockerHub | `docker login` |
| 推送镜像 | `docker push your-username/yishe-ps:latest` |
| 拉取镜像 | `docker pull your-username/yishe-ps:latest` |
| 删除镜像 | `docker rmi yishe-ps:latest` |
| 清理未使用镜像 | `docker image prune -a` |

## 注意事项

1. **首次构建时间较长**：需要下载 Windows Server Core 基础镜像（约 4GB）
2. **需要足够的磁盘空间**：Windows 容器镜像较大
3. **必须在 Windows 容器模式**：Linux 容器模式无法构建
4. **网络要求**：需要访问 Docker Hub 和 Chocolatey 源

