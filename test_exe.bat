@echo off
chcp 65001 >nul
cd /d "%~dp0dist\server"
echo Testing server.exe...
echo.
server.exe --help
echo.
echo Exit code: %ERRORLEVEL%
pause

