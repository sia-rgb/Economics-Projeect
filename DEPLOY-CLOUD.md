# 云平台一键部署指南

最简单的部署方式：**5分钟部署，给个网址就能用**

---

## 🚀 方案一：Railway（推荐，最简单）

### 为什么选择 Railway？
- ✅ 完全免费（有使用额度）
- ✅ 自动 HTTPS
- ✅ 自动部署
- ✅ 无需服务器管理
- ✅ 5分钟搞定

### 部署步骤：

#### 1. 准备代码（如果还没上传到 GitHub）

```bash
# 在项目目录下执行
git init
git add .
git commit -m "Initial commit"
git branch -M main

# 在 GitHub 创建新仓库，然后：
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

#### 2. 部署到 Railway

1. **访问 Railway**
   - 打开 https://railway.app/
   - 点击 "Start a New Project"

2. **连接 GitHub**
   - 选择 "Deploy from GitHub repo"
   - 授权 Railway 访问你的 GitHub
   - 选择你的代码仓库

3. **Railway 会自动检测并部署**
   - Railway 会自动识别项目类型
   - 等待部署完成（约 2-3 分钟）

4. **配置环境变量**
   - 点击项目 → Settings → Variables
   - 添加以下环境变量：
     ```
     DEEPSEEK_API_KEY = sk-你的真实key
     PORT = 8000
     ```
   - Railway 会自动重启服务

5. **获取网址**
   - 点击项目 → Settings → Domains
   - Railway 会自动分配一个网址，例如：`https://your-app.railway.app`
   - 也可以自定义域名

**完成！** 把这个网址发给其他人就能用了。

---

## 🌐 方案二：Render（同样简单）

### 部署步骤：

1. **访问 Render**
   - 打开 https://render.com/
   - 使用 GitHub 账号登录

2. **创建 Web Service**
   - 点击 "New" → "Web Service"
   - 连接你的 GitHub 仓库

3. **配置服务**
   - **Name**: epub-analyst（任意名称）
   - **Environment**: Python 3
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Start Command**: `cd backend && pip install -r requirements.txt && gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

4. **配置环境变量**
   - 在 Environment Variables 中添加：
     ```
     DEEPSEEK_API_KEY = sk-你的真实key
     PORT = 8000
     ```

5. **部署**
   - 点击 "Create Web Service"
   - 等待部署完成（约 5 分钟）

6. **获取网址**
   - Render 会自动分配：`https://your-app.onrender.com`

**完成！**

---

## 🐳 方案三：Fly.io（免费，速度快）

### 部署步骤：

1. **安装 Fly CLI**
   ```bash
   # Windows (PowerShell)
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   
   # Mac/Linux
   curl -L https://fly.io/install.sh | sh
   ```

2. **登录 Fly.io**
   ```bash
   fly auth login
   ```

3. **初始化项目**
   ```bash
   fly launch
   ```
   - 选择应用名称
   - 选择区域（选择离你最近的）
   - 不创建 Postgres（选择 No）

4. **配置环境变量**
   ```bash
   fly secrets set DEEPSEEK_API_KEY=sk-你的真实key
   ```

5. **部署**
   ```bash
   fly deploy
   ```

6. **获取网址**
   ```bash
   fly open
   ```

**完成！**

---

## 📋 部署前检查清单

- [ ] 代码已上传到 GitHub
- [ ] 已获取 DeepSeek API Key（https://platform.deepseek.com/）
- [ ] 已选择云平台（Railway / Render / Fly.io）

---

## ⚙️ 环境变量配置

所有平台都需要配置以下环境变量：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `DEEPSEEK_API_KEY` | `sk-xxx` | **必填**，你的 DeepSeek API Key |
| `PORT` | `8000` | 可选，端口号（Railway 会自动设置） |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` | 可选，API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 可选，模型名称 |

---

## 🔧 故障排查

### 部署失败？

1. **检查构建日志**
   - Railway/Render: 在项目页面查看 Build Logs
   - 查看错误信息

2. **常见问题**
   - **Node.js 未找到**：确保 `frontend/package.json` 存在
   - **Python 依赖失败**：检查 `backend/requirements.txt`
   - **环境变量未设置**：确保 `DEEPSEEK_API_KEY` 已配置

3. **测试本地构建**
   ```bash
   # 构建前端
   cd frontend
   npm install
   npm run build
   
   # 测试后端
   cd ../backend
   pip install -r requirements.txt
   python main.py
   ```

### 应用无法访问？

1. **检查服务状态**
   - Railway: 项目页面查看服务状态
   - Render: 查看服务日志

2. **检查环境变量**
   - 确保 `DEEPSEEK_API_KEY` 已正确设置
   - 检查是否有拼写错误

3. **查看日志**
   - 在平台的控制台查看实时日志
   - 查找错误信息

---

## 💡 推荐方案对比

| 平台 | 难度 | 免费额度 | 速度 | 推荐度 |
|------|------|----------|------|--------|
| **Railway** | ⭐ 最简单 | $5/月免费 | 快 | ⭐⭐⭐⭐⭐ |
| **Render** | ⭐⭐ 简单 | 免费 | 中等 | ⭐⭐⭐⭐ |
| **Fly.io** | ⭐⭐⭐ 中等 | 免费 | 很快 | ⭐⭐⭐⭐ |

**推荐：Railway** - 最简单，5分钟搞定！

---

## 🎯 快速开始（Railway）

**最快方式：**

1. 代码上传到 GitHub ✅
2. 访问 https://railway.app/ ✅
3. 点击 "Deploy from GitHub" ✅
4. 选择仓库 ✅
5. 添加环境变量 `DEEPSEEK_API_KEY` ✅
6. 复制网址发给其他人 ✅

**就这么简单！**

---

## 📞 需要帮助？

如果遇到问题：
1. 查看平台的构建日志
2. 检查环境变量配置
3. 确认代码已正确上传到 GitHub

祝部署顺利！🎉
