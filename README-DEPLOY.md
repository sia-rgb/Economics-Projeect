# 🚀 一键部署到云平台 - 给个网址就能用

## 最简单的部署方式

**目标**：5分钟部署，给其他人一个网址就能用，无需安装任何东西。

---

## ⚡ 快速开始（3步完成）

### 第1步：上传代码到 GitHub

如果代码还没上传：

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main

# 在 GitHub 创建新仓库，然后：
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

### 第2步：部署到 Railway

1. 访问 https://railway.app/
2. 点击 "Start a New Project" → "Deploy from GitHub repo"
3. 选择你的仓库
4. 等待自动部署（约2-3分钟）

### 第3步：配置 API Key

1. 在 Railway 项目页面 → Settings → Variables
2. 添加环境变量：
   ```
   DEEPSEEK_API_KEY = sk-你的真实key
   ```
3. Railway 会自动重启

**完成！** Railway 会给你一个网址，例如：`https://your-app.railway.app`

把这个网址发给其他人，他们打开就能用！

---

## 📖 详细步骤

查看 `DEPLOY-CLOUD.md` 获取：
- Railway 详细部署步骤
- Render 部署方法
- Fly.io 部署方法
- 故障排查指南

---

## 🔑 获取 DeepSeek API Key

1. 访问 https://platform.deepseek.com/
2. 注册/登录账号
3. 创建 API Key
4. 复制 Key（格式：`sk-xxx`）

---

## ✅ 部署检查清单

- [ ] 代码已上传到 GitHub
- [ ] 已获取 DeepSeek API Key
- [ ] 已在 Railway 配置环境变量
- [ ] 已测试访问网址

---

## 💡 推荐平台

**Railway** - 最简单，推荐新手使用
- 免费额度：$5/月
- 自动 HTTPS
- 5分钟部署

**Render** - 同样简单
- 完全免费
- 自动部署
- 适合个人项目

**Fly.io** - 速度快
- 免费额度充足
- 全球 CDN
- 适合生产环境

---

## 🆘 遇到问题？

1. 查看 `DEPLOY-CLOUD.md` 中的故障排查部分
2. 检查平台的构建日志
3. 确认环境变量已正确配置

---

**就这么简单！5分钟部署，给个网址就能用！** 🎉
