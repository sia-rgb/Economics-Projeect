# CLAUDE.md

本文件为 Claude Code 在此代码库中工作时提供指导。

## 概述

此项目是一个 EPUB 分析助手，提供网页界面，使用 DeepSeek API 对 EPUB（如 The Economist）中的每一篇文章进行中文结构化分析，并汇总到一个 Word 文档中供下载。

项目采用前后端分离架构：
- **后端**：Python FastAPI，负责接收 EPUB、解析章节、调用 DeepSeek API、生成 Word 文档
- **前端**：React + Vite + Tailwind CSS，负责文件上传、进度展示与结果下载

## 常用命令

### 开发环境启动
- `start.bat`：一键启动脚本（Windows），同时启动后端和前端并打开浏览器
- 手动启动：
  ```powershell
  # 启动后端
  cd backend
  uvicorn main:app --reload --port 8000

  # 启动前端
  cd frontend
  npm run dev
  ```
- 访问前端：`http://localhost:5173`
- 后端健康检查：`http://localhost:8000/health`

### 依赖安装
- Python 依赖：
  ```powershell
  cd backend
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- Node.js 依赖：
  ```powershell
  cd frontend
  npm install
  ```

### 构建与部署
- 构建前端：
  ```bash
  cd frontend
  npm run build
  ```
- 使用 Docker：
  ```bash
  docker-compose up -d
  ```
- 部署到 GitHub Pages：
  ```bash
  cd frontend
  npm run predeploy
  npm run deploy
  ```

## 项目结构

```
Economics-Projeect/
├── backend/                    # FastAPI 后端
│   ├── main.py                # 主应用入口
│   ├── deepseek_client.py     # DeepSeek API 客户端
│   ├── epub_processing.py     # EPUB 解析模块
│   ├── doc_builder.py         # Word 文档生成模块
│   ├── requirements.txt       # Python 依赖
│   └── .env.example           # 环境变量示例
├── frontend/                  # React 前端
│   ├── src/
│   │   ├── main.tsx          # 应用入口
│   │   ├── upload-page.tsx   # 上传页面组件
│   │   └── index.css         # 全局样式
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts        # Vite 配置（代理设置）
│   └── tailwind.config.js    # Tailwind 配置
├── start.bat                 # 一键启动脚本（Windows）
├── start.sh                  # 启动脚本（Unix）
├── docker-compose.yml        # Docker 编排配置
├── README.md                 # 项目详细说明
├── DEPLOY.md                 # 部署指南
└── CLAUDE.md                 # 本文件
```

## 开发工作流程

### 环境设置
1. 确保安装 Python 3.10+ 和 Node.js（LTS 版本）
2. 配置 DeepSeek API 密钥：
   - 在 `backend/` 目录创建 `.env` 文件
   - 添加 `DEEPSEEK_API_KEY=sk-你的真实key`
   - 可选设置 `DEEPSEEK_API_BASE` 和 `DEEPSEEK_MODEL`

### 本地开发
1. 启动后端：`cd backend && uvicorn main:app --reload --port 8000`
2. 启动前端：`cd frontend && npm run dev`
3. 访问 `http://localhost:5173` 进行测试

### 代码修改指南
- **后端修改**：主要逻辑在 `backend/main.py`，API 端点处理 EPUB 上传和分析
- **前端修改**：主要界面在 `frontend/src/upload-page.tsx`，处理文件上传和状态展示
- **EPUB 解析**：`backend/epub_processing.py` 包含文章提取逻辑
- **DeepSeek 集成**：`backend/deepseek_client.py` 处理 API 调用和格式化
- **Word 生成**：`backend/doc_builder.py` 使用 python-docx 创建文档

### 测试
- 后端 API 测试：可使用 `/api/debug-analyze-first` 端点测试单篇文章分析
- 前端测试：手动上传 EPUB 文件验证完整流程
- DeepSeek 连接测试：访问 `/api/debug-deepseek` 验证 API 密钥配置

## 注意事项

### API 密钥与安全
- **切勿提交** `.env` 文件到版本控制
- API 密钥通过环境变量 `DEEPSEEK_API_KEY` 读取
- 生产环境应使用安全的密钥管理方案

### 性能与超时
- EPUB 分析可能耗时较长（5-15 分钟），代理超时已设置为 5 分钟（300000ms）
- 可在 `frontend/vite.config.ts` 中调整 `timeout` 值
- 后端使用并发控制 (`MAX_PARALLEL_TASKS`) 避免 API 限流

### 文件处理
- 上传的 EPUB 文件会临时保存到磁盘，处理完成后自动删除
- 生成的 Word 文档通过流式响应返回，避免内存占用过大
- 支持非 ASCII 文件名（使用 RFC 5987 编码）

### 漫画文章过滤
- 系统会自动过滤识别为漫画的文章（基于标题和内容关键词）
- 过滤逻辑在 `_is_cartoon_article` 和 `_is_cartoon_translation` 函数中

### 语言要求
- 所有对话响应、解释、代码注释和新生成的文档必须使用**简体中文**
- 用户界面和文档应保持中文友好
- DeepSeek 分析结果已预设为中文输出格式

## 给 Claude 的指导

### 代码风格与约定
- 遵循现有代码的命名规范和结构
- Python 代码使用类型注解（type hints）
- React 组件使用函数组件和 Hooks
- 添加新功能时，优先考虑与现有架构的一致性

### 错误处理
- 后端 API 应返回适当的 HTTP 状态码和错误信息
- 使用 `HTTPException` 处理客户端错误
- 捕获并记录未处理的异常，避免泄露敏感信息
- 前端应友好地显示错误状态

### 添加新功能
1. 先理解现有代码结构和工作流程
2. 如有必要，更新 `README.md` 和本文件
3. 确保向后兼容性，或提供迁移路径
4. 测试完整流程，从上传到下载

### 调试帮助
- 后端提供多个调试端点：
  - `/api/debug-analyze-first`：仅分析第一篇文章
  - `/api/debug-deepseek`：测试 DeepSeek 连接
  - `last_error.txt`：记录最近错误日志
- 前端开发时可利用 Vite 的热重载和开发工具

### 部署注意事项
- 生产构建时，前端通过 `npm run build` 生成静态文件
- 后端需要正确配置 CORS 和静态文件服务
- Docker 镜像包含完整的前后端，适合云部署
- GitHub Pages 部署需要设置正确的 base 路径

## 相关文档

- [README.md](./README.md)：详细用户指南
- [DEPLOY.md](./DEPLOY.md)：部署指南
- [DEPLOY-GITHUB-PAGES.md](./DEPLOY-GITHUB-PAGES.md)：GitHub Pages 部署说明
- [DEPLOY-CLOUD.md](./DEPLOY-CLOUD.md)：云平台部署说明