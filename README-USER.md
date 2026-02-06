# EPUB 分析助手 - 用户使用指南

欢迎使用 EPUB 分析助手！本工具可以帮助您将 EPUB 文件（如 The Economist）中的文章自动分析并生成中文 Word 文档。

## 快速开始

### 第一步：环境准备

确保您的电脑已安装：

- **Python 3.10 或更高版本**（推荐 3.11+）
  - 下载地址：https://www.python.org/downloads/
  - 安装时请勾选 "Add Python to PATH"

- **Node.js**（LTS 版本）
  - 下载地址：https://nodejs.org/
  - 安装完成后，打开命令行输入 `node -v` 验证安装

### 第二步：安装依赖

#### 方法一：使用安装脚本（推荐）

1. 双击运行 `install.bat`
2. 脚本会自动检测环境并安装所需依赖
3. 按照提示输入 DeepSeek API Key

#### 方法二：手动安装

1. **安装 Python 依赖**

   打开命令行，进入 `backend` 目录：

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate    # Windows
   # 或 source .venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

2. **安装前端依赖**

   打开新的命令行窗口，进入 `frontend` 目录：

   ```bash
   cd frontend
   npm install
   ```

### 第三步：配置 API Key

1. 在 `backend` 目录下创建 `.env` 文件（注意：文件名就是 `.env`，没有扩展名）

2. 编辑 `.env` 文件，添加以下内容：

   ```env
   DEEPSEEK_API_KEY=sk-你的真实key
   DEEPSEEK_API_BASE=https://api.deepseek.com
   DEEPSEEK_MODEL=deepseek-chat
   ```

3. 将 `sk-你的真实key` 替换为您从 DeepSeek 获取的真实 API Key

   - 获取 API Key：访问 https://platform.deepseek.com/
   - 注册账号并创建 API Key

### 第四步：启动应用

#### 方法一：一键启动（推荐）

双击运行 `start.bat`，脚本会自动：
- 启动后端服务
- 启动前端服务
- 自动打开浏览器

#### 方法二：手动启动

1. **启动后端**

   打开命令行，进入 `backend` 目录：

   ```bash
   cd backend
   .venv\Scripts\activate    # Windows
   uvicorn main:app --reload --port 8000
   ```

   看到 `Application startup complete` 表示启动成功。

2. **启动前端**

   打开新的命令行窗口，进入 `frontend` 目录：

   ```bash
   cd frontend
   npm run dev
   ```

3. **访问应用**

   打开浏览器，访问：`http://localhost:5173`

### 第五步：使用应用

1. 在网页上点击"选择文件"，上传 EPUB 文件
2. 点击"开始分析并生成 Word"
3. 等待分析完成（进度条会显示进度）
4. 分析完成后，点击"下载 Word 文档"按钮

## 常见问题

### Q1: 提示"未找到 Node.js"或"未找到 Python"

**解决方法：**
- 确认已正确安装 Node.js 和 Python
- 检查是否添加到系统 PATH 环境变量
- 重新打开命令行窗口再试

### Q2: 提示"未加载到指定环境变量"

**解决方法：**
- 确认 `.env` 文件在 `backend` 目录下
- 确认文件名是 `.env`（不是 `.env.txt`）
- 确认 `DEEPSEEK_API_KEY=sk-xxx` 格式正确，没有多余空格

### Q3: 前端显示"Failed to fetch"

**解决方法：**
- 确认后端已启动（访问 http://localhost:8000/health 应返回 `{"status":"ok"}`）
- 确认前端和后端都在运行
- 检查防火墙是否阻止了端口

### Q4: 分析时间很长

**说明：**
- 这是正常现象，一本完整的 EPUB 可能需要 5-15 分钟
- 进度条是估算值，实际完成时间取决于文章数量和长度
- 请耐心等待，不要关闭浏览器或服务

### Q5: 如何更新应用？

**方法：**
1. 下载新版本
2. 备份您的 `.env` 文件
3. 替换旧文件
4. 重新运行 `install.bat` 或手动安装依赖

## 系统要求

- **操作系统**：Windows 10/11, macOS, Linux
- **Python**：3.10 或更高版本
- **Node.js**：LTS 版本（推荐 18.x 或更高）
- **内存**：至少 2GB 可用内存
- **网络**：需要能够访问 DeepSeek API

## 技术支持

如遇到问题，请检查：

1. Python 和 Node.js 版本是否符合要求
2. `.env` 文件配置是否正确
3. 网络连接是否正常
4. 防火墙是否允许端口 8000 和 5173

## 注意事项

1. **API Key 安全**：请妥善保管您的 API Key，不要分享给他人
2. **文件大小**：建议 EPUB 文件大小不超过 50MB
3. **处理时间**：大文件可能需要较长时间，请耐心等待
4. **网络要求**：需要稳定的网络连接以访问 DeepSeek API

---

祝您使用愉快！
