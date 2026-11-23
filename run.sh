#!/usr/bin/env bash
# 小熙客服一键启动（Linux / macOS / Git Bash）
cd "$(dirname "$0")"
python -m pip install -r requirements.txt -q
echo "启动中，浏览器打开: http://127.0.0.1:8000"
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
