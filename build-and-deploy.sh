#!/bin/bash
# 构建和部署脚本

set -e

echo "开始构建 EPUB 分析助手..."

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "错误: 未找到 Node.js，请先安装 Node.js"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python3"
    exit 1
fi

# 构建前端
echo "构建前端..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi
npm run build
cd ..

# 检查构建结果
if [ ! -d "frontend/dist" ]; then
    echo "错误: 前端构建失败，未找到 dist 目录"
    exit 1
fi

echo "前端构建完成！"

# 检查后端依赖
echo "检查后端依赖..."
cd backend
if [ ! -d ".venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告: 未找到 .env 文件，请创建并配置 DEEPSEEK_API_KEY"
    echo "示例:"
    echo "DEEPSEEK_API_KEY=sk-your-key"
    echo "DEEPSEEK_API_BASE=https://api.deepseek.com"
    echo "DEEPSEEK_MODEL=deepseek-chat"
fi

cd ..

echo ""
echo "构建完成！"
echo ""
echo "启动服务:"
echo "  cd backend"
echo "  source .venv/bin/activate  # Linux/Mac"
echo "  uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo "或使用 gunicorn (生产环境):"
echo "  gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"
echo ""
