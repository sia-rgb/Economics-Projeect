# GitHub Pages + 后端混合部署方案

## 方案说明

**前端**：部署到 GitHub Pages（免费、简单）  
**后端**：部署到 Railway/Render（免费）

这样你就可以：
- ✅ 前端网址：`https://你的用户名.github.io/仓库名`（GitHub Pages）
- ✅ 后端网址：`https://your-app.railway.app`（Railway）
- ✅ 两个都是免费的！

---

## 部署步骤

### 第一步：部署后端到 Railway（5分钟）

1. **访问 Railway**
   - 打开 https://railway.app/
   - 点击 "Deploy from GitHub repo"
   - 选择你的仓库

2. **配置环境变量**
   - 在 Railway 项目 → Settings → Variables
   - 添加：`DEEPSEEK_API_KEY = sk-你的真实key`

3. **获取后端网址**
   - Railway 会给你一个网址，例如：`https://your-app.railway.app`
   - **记住这个网址，后面要用！**

### 第二步：修改前端配置

需要修改前端代码，让它调用远程后端：

1. **创建环境变量文件**

   在 `frontend` 目录创建 `.env.production` 文件：

   ```env
   VITE_API_BASE_URL=https://your-app.railway.app
   ```

   ⚠️ **重要**：将 `your-app.railway.app` 替换为你的 Railway 后端网址！

2. **修改前端代码调用后端**

   需要修改 `frontend/src/upload-page.tsx`，将 `/api` 改为使用环境变量。

### 第三步：部署前端到 GitHub Pages

1. **安装 GitHub Pages 插件**

   ```bash
   cd frontend
   npm install --save-dev gh-pages
   ```

2. **修改 package.json**

   添加以下脚本：

   ```json
   {
     "scripts": {
       "predeploy": "npm run build",
       "deploy": "gh-pages -d dist"
     }
   }
   ```

3. **配置 GitHub Pages**

   - 在 GitHub 仓库 → Settings → Pages
   - Source 选择：`gh-pages` 分支
   - 点击 Save

4. **部署**

   ```bash
   npm run deploy
   ```

5. **获取前端网址**

   - GitHub 会自动给你：`https://你的用户名.github.io/仓库名`
   - 把这个网址发给其他人就能用！

---

## 详细配置步骤

### 1. 修改前端代码以支持环境变量

需要修改 `frontend/src/upload-page.tsx`：

将：
```typescript
const response = await fetch("/api/analyze-epub", {
```

改为：
```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const response = await fetch(`${API_BASE}/api/analyze-epub`, {
```

### 2. 配置 CORS

后端需要允许 GitHub Pages 域名访问。修改 `backend/main.py`：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://你的用户名.github.io",  # GitHub Pages 域名
        "http://localhost:5173",  # 本地开发
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 完整工作流程

1. **后端部署**（Railway）- 5分钟
   - 部署后端
   - 获取后端网址
   - 配置 API Key

2. **前端配置**（本地）- 2分钟
   - 创建 `.env.production`
   - 修改代码使用环境变量
   - 配置 CORS

3. **前端部署**（GitHub Pages）- 2分钟
   - 运行 `npm run deploy`
   - 获取前端网址

4. **完成！**
   - 把前端网址发给其他人
   - 他们打开就能用！

---

## 优点

- ✅ GitHub Pages 完全免费
- ✅ Railway 免费额度充足
- ✅ 前端更新简单（只需 `npm run deploy`）
- ✅ 两个服务独立，互不影响

## 缺点

- ⚠️ 需要配置两个服务
- ⚠️ 需要修改前端代码

---

## 更简单的替代方案

如果你觉得这样还是太复杂，**推荐直接用 Railway 部署整个应用**（前端+后端一起），这样：

- ✅ 只需要一个网址
- ✅ 只需要配置一次
- ✅ 更简单！

查看 `DEPLOY-CLOUD.md` 了解 Railway 一键部署方案。
