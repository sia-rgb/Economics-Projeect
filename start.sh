#!/bin/bash
# 云平台启动脚本

set -e  # 遇到错误立即退出

echo "开始部署..."

# 构建前端
echo "构建前端..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi
echo "构建前端应用..."
npm run build
cd ..

# 检查前端构建是否成功
if [ ! -d "frontend/dist" ]; then
    echo "错误: 前端构建失败，未找到 dist 目录"
    exit 1
fi

echo "前端构建完成"

# 安装后端依赖
echo "安装后端依赖..."
cd backend
pip install -r requirements.txt gunicorn
cd ..

# 启动服务
echo "启动后端服务..."
PORT=${PORT:-8000}
cd backend
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
