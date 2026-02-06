# GitHub Pages 部署指南（最简单）

## 方案说明

**前端**：GitHub Pages（免费）  
**后端**：Railway（免费）

这样你就可以：
- ✅ 前端网址：`https://你的用户名.github.io/Economics-Projeect`
- ✅ 完全免费
- ✅ 只需要一个前端网址发给别人

---

## 🚀 快速部署（5分钟）

### 第1步：部署后端到 Railway（2分钟）

1. 访问 https://railway.app/
2. 点击 "Deploy from GitHub repo"
3. 选择你的仓库
4. 在 Settings → Variables 添加：
   ```
   DEEPSEEK_API_KEY = sk-你的真实key
   ```
5. **复制后端网址**，例如：`https://your-app.railway.app`

### 第2步：配置前端（1分钟）

1. 在 `frontend` 目录创建 `.env.production` 文件：

   ```env
   VITE_API_BASE_URL=https://your-app.railway.app
   ```

   ⚠️ **重要**：替换为你的 Railway 后端网址！

2. 安装 GitHub Pages 部署工具：

   ```bash
   cd frontend
   npm install --save-dev gh-pages
   ```

### 第3步：配置后端 CORS（1分钟）

修改 `backend/main.py`，添加你的 GitHub Pages 域名：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://你的用户名.github.io",  # 替换为你的 GitHub 用户名
        "http://localhost:5173",  # 本地开发
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 第4步：部署前端到 GitHub Pages（1分钟）

1. 构建并部署：

   ```bash
   cd frontend
   npm run deploy
   ```

2. 配置 GitHub Pages：
   - 在 GitHub 仓库 → Settings → Pages
   - Source 选择：`gh-pages` 分支
   - 点击 Save

3. **获取前端网址**：
   - `https://你的用户名.github.io/Economics-Projeect`
   - 把这个网址发给其他人就能用！

---

## ✅ 完成！

现在你有：
- 前端：`https://你的用户名.github.io/Economics-Projeect`（GitHub Pages）
- 后端：`https://your-app.railway.app`（Railway）

**只需要把前端网址发给别人，他们打开就能用！**

---

## 🔄 更新部署

当代码更新后：

1. **更新后端**：Railway 会自动重新部署
2. **更新前端**：
   ```bash
   cd frontend
   npm run deploy
   ```

---

## ⚠️ 注意事项

1. **base 路径**：如果仓库名不是 `Economics-Projeect`，需要修改 `vite.config.ts` 中的 `base` 配置
2. **CORS**：确保后端允许你的 GitHub Pages 域名访问
3. **环境变量**：`.env.production` 文件不要提交到 Git（已在 .gitignore）

---

## 🆘 遇到问题？

1. **前端无法连接后端**：
   - 检查 `.env.production` 中的 URL 是否正确
   - 检查后端 CORS 配置

2. **GitHub Pages 404**：
   - 确认已选择 `gh-pages` 分支
   - 等待几分钟让 GitHub 更新

3. **构建失败**：
   - 检查 `npm run build` 是否有错误
   - 确认所有依赖已安装

---

## 💡 更简单的方案

如果觉得配置两个服务太麻烦，**推荐直接用 Railway 部署整个应用**：

- ✅ 只需要一个网址
- ✅ 只需要配置一次
- ✅ 更简单！

查看 `DEPLOY-CLOUD.md` 了解 Railway 一键部署。
