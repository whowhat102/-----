@echo off
chcp 65001 >nul
cd /d %~dp0
echo [灵犀客服] 正在安装依赖（首次约 1 分钟）...
python -m pip install -r requirements.txt -q
echo.
echo [灵犀客服] 启动中，浏览器打开: http://127.0.0.1:8000
echo 按 Ctrl+C 停止服务
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
pause
