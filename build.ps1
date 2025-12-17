# PowerShell 构建脚本 - 一键构建 Docker 镜像并发布到 DockerHub
# 使用方法: .\build.ps1 [版本号] [DockerHub用户名]
# 示例: .\build.ps1 1.0.0 yourusername

param(
    [string]$Version = "latest",
    [string]$DockerHubUser = ""
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  yishe-ps Docker 构建脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Docker 是否运行
Write-Host "[1/5] 检查 Docker 环境..." -ForegroundColor Yellow
try {
    docker version | Out-Null
    Write-Host "✓ Docker 已运行" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker 未运行，请先启动 Docker Desktop" -ForegroundColor Red
    exit 1
}

# 检查是否在 Windows 容器模式
Write-Host "[2/5] 检查容器模式..." -ForegroundColor Yellow
$containerMode = docker version --format '{{.Server.Os}}'
if ($containerMode -ne "windows") {
    Write-Host "⚠ 当前不是 Windows 容器模式" -ForegroundColor Yellow
    Write-Host "  正在切换到 Windows 容器模式..." -ForegroundColor Yellow
    & $Env:ProgramFiles\Docker\Docker\DockerCli.exe -SwitchDaemon
    Write-Host "  请重新运行此脚本" -ForegroundColor Yellow
    exit 0
}
Write-Host "✓ Windows 容器模式已启用" -ForegroundColor Green

# 确定镜像名称
if ($DockerHubUser -eq "") {
    Write-Host ""
    $DockerHubUser = Read-Host "请输入 DockerHub 用户名"
    if ($DockerHubUser -eq "") {
        Write-Host "✗ 必须提供 DockerHub 用户名" -ForegroundColor Red
        exit 1
    }
}

$ImageName = "${DockerHubUser}/yishe-ps"
$FullImageName = "${ImageName}:${Version}"

Write-Host ""
Write-Host "[3/5] 构建 Docker 镜像..." -ForegroundColor Yellow
Write-Host "  镜像名称: $FullImageName" -ForegroundColor Gray

docker build -t $FullImageName -t "${ImageName}:latest" .

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 构建失败" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 构建成功" -ForegroundColor Green

# 测试镜像
Write-Host ""
Write-Host "[4/5] 测试镜像..." -ForegroundColor Yellow
docker run --rm $FullImageName python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 测试失败" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 测试通过" -ForegroundColor Green

# 发布到 DockerHub
Write-Host ""
Write-Host "[5/5] 发布到 DockerHub..." -ForegroundColor Yellow
Write-Host "  是否发布到 DockerHub? (Y/N)" -ForegroundColor Gray
$confirm = Read-Host
if ($confirm -eq "Y" -or $confirm -eq "y") {
    Write-Host "  正在推送镜像..." -ForegroundColor Gray
    docker push $FullImageName
    docker push "${ImageName}:latest"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 推送失败，请检查 DockerHub 登录状态" -ForegroundColor Red
        Write-Host "  运行: docker login" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "✓ 发布成功" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  镜像已发布到 DockerHub" -ForegroundColor Cyan
    Write-Host "  拉取命令: docker pull $FullImageName" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
} else {
    Write-Host "  跳过发布" -ForegroundColor Gray
}

Write-Host ""
Write-Host "构建完成！" -ForegroundColor Green

