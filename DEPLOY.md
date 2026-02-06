# 部署指南

本指南说明如何将 EPUB 分析助手部署到公网，让其他人通过 URL 直接访问。

## 部署方式

### 方式一：单服务器部署（推荐）

将前端和后端部署在同一台服务器上，后端同时提供 API 和静态文件服务。

#### 1. 服务器要求

- Python 3.10+
- 至少 2GB 内存
- 公网 IP 或域名
- 开放端口（默认 8000）

#### 2. 部署步骤

**步骤1：上传代码到服务器**

```bash
# 使用 git 或 scp 上传代码
scp -r Economics-Projeect user@your-server:/opt/
```

**步骤2：安装依赖**

```bash
# 进入项目目录
cd /opt/Economics-Projeect

# 安装 Python 依赖
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 安装前端依赖并构建
cd ../frontend
npm install
npm run build
```

**步骤3：配置环境变量**

在 `backend` 目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=sk-你的真实key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

**步骤4：启动服务**

使用 uvicorn 启动（开发环境）：

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

使用 gunicorn 启动（生产环境，推荐）：

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**步骤5：配置反向代理（可选但推荐）**

使用 Nginx 作为反向代理，提供 HTTPS 支持：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 支持长时间请求
        proxy_read_timeout 7200s;
        proxy_send_timeout 7200s;
    }
}
```

配置 HTTPS（使用 Let's Encrypt）：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

#### 3. 使用 systemd 管理服务（Linux）

创建服务文件 `/etc/systemd/system/epub-analyst.service`：

```ini
[Unit]
Description=EPUB Analyst Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/opt/Economics-Projeect/backend
Environment="PATH=/opt/Economics-Projeect/backend/.venv/bin"
ExecStart=/opt/Economics-Projeect/backend/.venv/bin/gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable epub-analyst
sudo systemctl start epub-analyst
sudo systemctl status epub-analyst
```

### 方式二：Docker 部署

#### 1. 创建 Dockerfile

在项目根目录创建 `Dockerfile`：

```dockerfile
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
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ .

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist ./../frontend/dist

# 设置环境变量
ENV DEEPSEEK_API_KEY=""
ENV DEEPSEEK_API_BASE="https://api.deepseek.com"
ENV DEEPSEEK_MODEL="deepseek-chat"

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

#### 2. 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  epub-analyst:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - DEEPSEEK_API_BASE=${DEEPSEEK_API_BASE:-https://api.deepseek.com}
      - DEEPSEEK_MODEL=${DEEPSEEK_MODEL:-deepseek-chat}
    restart: unless-stopped
```

#### 3. 构建和运行

```bash
# 构建镜像
docker-compose build

# 运行容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 方式三：云平台部署

#### Vercel / Netlify（仅前端）+ 独立后端服务器

如果使用云平台部署前端，需要：

1. 修改前端 API 调用，使用完整 URL
2. 配置 CORS，允许前端域名访问
3. 分别部署前端和后端

## 安全建议

1. **API Key 安全**
   - 不要将 API Key 提交到代码仓库
   - 使用环境变量或密钥管理服务
   - 定期轮换 API Key

2. **CORS 配置**
   - 生产环境不要使用 `allow_origins=["*"]`
   - 指定具体的允许域名：
   ```python
   allow_origins=["https://your-domain.com", "https://www.your-domain.com"]
   ```

3. **HTTPS**
   - 使用 HTTPS 加密传输
   - 配置 SSL 证书（Let's Encrypt 免费）

4. **访问控制**
   - 考虑添加身份验证（可选）
   - 限制上传文件大小
   - 添加速率限制

## 更新部署

当代码更新时：

1. 拉取最新代码
2. 重新构建前端：`cd frontend && npm run build`
3. 重启服务：`sudo systemctl restart epub-analyst` 或 `docker-compose restart`

## 故障排查

1. **检查服务状态**
   ```bash
   sudo systemctl status epub-analyst
   ```

2. **查看日志**
   ```bash
   sudo journalctl -u epub-analyst -f
   ```

3. **检查端口**
   ```bash
   netstat -tlnp | grep 8000
   ```

4. **测试 API**
   ```bash
   curl http://localhost:8000/health
   ```

## 性能优化

1. **使用 Gunicorn 多进程**
   ```bash
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **配置 Nginx 缓存静态文件**

3. **使用 CDN 加速静态资源**（如果前后端分离）

4. **监控和日志**
   - 使用 PM2 或 systemd 管理进程
   - 配置日志轮转
