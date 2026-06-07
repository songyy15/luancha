@echo off
chcp 65001 >nul
echo.
echo ================================
echo   路安查 v1.0  启动中...
echo ================================
echo.
echo 浏览器访问：http://localhost:8000
echo 按 Ctrl+C 停止服务
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
