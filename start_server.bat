@echo off
chcp 65001 >nul
title PSD 智能对象替换 API 服务
cd /d "%~dp0dist\server"
echo ========================================
echo PSD 智能对象替换 API 服务
echo ========================================
echo.
echo 正在启动服务...
echo 提示: 此窗口将保持打开，服务运行中
echo 提示: 按 Ctrl+C 可以停止服务
echo 提示: 关闭此窗口将停止服务
echo.
echo ========================================
echo.
server.exe
echo.
echo ========================================
echo 服务已停止
echo ========================================
pause

