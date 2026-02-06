# 构建前端
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# 运行后端
FROM python:3.11-slim
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 复制后端代码
COPY backend/ .

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist ./../frontend/dist

# 设置环境变量（可通过 docker-compose 或运行时覆盖）
ENV DEEPSEEK_API_KEY=""
ENV DEEPSEEK_API_BASE="https://api.deepseek.com"
ENV DEEPSEEK_MODEL="deepseek-chat"

# 暴露端口
EXPOSE 8000

# 启动命令（使用 shell 格式以支持环境变量）
CMD ["sh", "-c", "gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"]
