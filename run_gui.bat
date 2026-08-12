@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动转换器...
".venv\Scripts\pythonw.exe" main.py
if errorlevel 1 (
    echo.
    echo 启动失败，请确认 .venv 虚拟环境存在。
    pause
)
