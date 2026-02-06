#!/bin/bash
# 云平台启动脚本

# 构建前端（如果还没构建）
if [ ! -d "frontend/dist" ]; then
    echo "构建前端..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 启动服务
PORT=${PORT:-8000}
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
