# PowerShell 运行脚本 - 一键启动 Docker 容器
# 使用方法: .\run.ps1 [镜像名称]
# 示例: .\run.ps1 yourusername/yishe-ps:latest

param(
    [string]$ImageName = "yishe-ps:latest"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动 yishe-ps 容器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查镜像是否存在
Write-Host "[1/3] 检查镜像..." -ForegroundColor Yellow
$imageExists = docker images -q $ImageName
if (-not $imageExists) {
    Write-Host "✗ 镜像不存在: $ImageName" -ForegroundColor Red
    Write-Host "  请先构建或拉取镜像" -ForegroundColor Yellow
    Write-Host "  构建: .\build.ps1" -ForegroundColor Yellow
    Write-Host "  拉取: docker pull $ImageName" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ 镜像已找到" -ForegroundColor Green

# 停止并删除旧容器（如果存在）
Write-Host "[2/3] 清理旧容器..." -ForegroundColor Yellow
docker stop yishe-ps 2>$null
docker rm yishe-ps 2>$null
Write-Host "✓ 清理完成" -ForegroundColor Green

# 创建输出目录
$outputDir = Join-Path $PSScriptRoot "output"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

# 启动容器
Write-Host "[3/3] 启动容器..." -ForegroundColor Yellow
Write-Host "  容器名称: yishe-ps" -ForegroundColor Gray
Write-Host "  端口映射: 1595:1595" -ForegroundColor Gray
Write-Host "  输出目录: $outputDir" -ForegroundColor Gray
Write-Host ""

docker run -d `
    --name yishe-ps `
    -p 1595:1595 `
    -v "${outputDir}:C:\app\output" `
    -v "${PSScriptRoot}\examples:C:\app\examples" `
    --restart unless-stopped `
    $ImageName

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 启动失败" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 容器已启动" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  服务已启动" -ForegroundColor Cyan
Write-Host "  API 文档: http://localhost:1595/docs" -ForegroundColor Cyan
Write-Host "  Web UI: http://localhost:1595/ui" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "查看日志: docker logs -f yishe-ps" -ForegroundColor Yellow
Write-Host "停止容器: docker stop yishe-ps" -ForegroundColor Yellow
Write-Host "删除容器: docker rm yishe-ps" -ForegroundColor Yellow

