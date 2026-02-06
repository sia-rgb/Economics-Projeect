# TX Economics · EPUB 分析助手

本工具提供一个网页界面，用 DeepSeek 对 EPUB（如 The Economist）中的每一篇文章进行中文结构化分析，并汇总到一个 Word 文档中下载。

**项目根目录**：`C:\Users\xiayi\Economics-Projeect`

---

## 一、项目结构

- `start.bat`：一键启动脚本，双击可同时启动后端和前端并打开浏览器。
- `backend/`：FastAPI 后端，负责接收 EPUB、解析章节、调用 DeepSeek、生成 Word。
- `frontend/`：React + Vite + Tailwind 前端，负责文件上传、进度展示与结果下载。

---

## 二、环境准备

### 1. 必备软件

- Python 3.10+（建议 3.11 以上）
- Node.js（含 npm，建议 LTS 版本）
- 操作系统：Windows 10/11

### 2. Python 环境与依赖

```powershell
cd C:\Users\xiayi\Economics-Projeect\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Node 环境与依赖

```powershell
cd C:\Users\xiayi\Economics-Projeect\frontend
npm install
```

如果 `npm` / `node` 命令无法识别：

- 确认已安装 Node.js；
- 在「系统环境变量」中将 `C:\Program Files\nodejs\` 加入 `Path`；
- 重新打开 PowerShell 再执行。

### 4. PowerShell 执行策略（如 `npm -v` 报 SecurityError）

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

按提示确认后重新打开 PowerShell。

---

## 三、DeepSeek API Key 配置

后端通过环境变量 `DEEPSEEK_API_KEY` 读取 Key，推荐使用 `.env` 文件：

1. 在 `backend` 目录下创建文件 `.env`：

```env
DEEPSEEK_API_KEY=sk-你的真实key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

2. 确认文件名为 **`.env`**（不是 `.env.txt`），并与 `main.py` 同目录。

3. 启动后端时，如看到：

- `✅ .env 文件加载成功`：说明读取正常；
- `⚠️ 未加载到指定环境变量`：检查 `.env` 路径与变量名是否为 `DEEPSEEK_API_KEY`。

也可以直接在系统环境变量中设置 `DEEPSEEK_API_KEY`，效果等价。

---

## 四、启动方式

### 一键启动（推荐）

在项目根目录下双击 `start.bat`，将自动：

1. 在新窗口中启动后端（uvicorn）；
2. 在新窗口中启动前端（npm run dev）；
3. 约 5 秒后自动打开浏览器访问 `http://localhost:5173`。

关闭服务时，请分别在两个弹出的 CMD 窗口中按 `Ctrl+C` 或直接关闭窗口。

首次使用前，请确保已完成「环境准备」和「DeepSeek API Key 配置」。

---

### 手动启动

#### 1. 启动后端（FastAPI）

```powershell
cd C:\Users\xiayi\Economics-Projeect\backend
uvicorn main:app --reload --port 8000
```

验证是否正常：

- 浏览器访问 `http://localhost:8000/health`，应返回：

```json
{"status":"ok"}
```

#### 2. 启动前端（React + Vite）

```powershell
cd C:\Users\xiayi\Economics-Projeect\frontend
npm run dev
```

浏览器访问：

```text
http://localhost:5173
```

注意：务必通过 `http://localhost:5173` 访问页面，**不要直接双击 HTML 文件** 或用 `file://` 协议。

---

## 五、端口与代理配置

前端通过 Vite 代理调用后端，默认配置在 `frontend/vite.config.ts`：

```ts
server: {
  port: 5173,
  proxy: {
    "/api": {
      target: "http://127.0.0.1:8000",
      changeOrigin: true,
      timeout: 300000 // 允许长时间分析（5 分钟）
    }
  }
}
```

- 若后端端口修改，请同步更新 `target`；
- 建议使用 `127.0.0.1` 避免某些环境下 `localhost` 的 IPv4/IPv6 解析问题。

---

## 六、常见问题排查（FAQ）

### 1. 前端显示 "Failed to fetch"

可能原因：

1. **后端未启动或端口不一致**
   - 确认已在 `backend` 目录运行 `uvicorn main:app --reload --port 8000`；
   - 浏览器访问 `http://localhost:8000/health` 是否返回 `{"status":"ok"}`；
   - 若后端端口不是 8000，需同步修改 `vite.config.ts` 的代理 `target`。

2. **Vite 代理超时**
   - 分析一本完整 EPUB 可能需要数分钟，如果代理默认超时过短会中断连接；
   - 已在代理中设置 `timeout: 300000`，如仍不够可适当增加。

3. **访问方式错误**
   - 必须通过 `npm run dev` 启动的地址 `http://localhost:5173` 访问；
   - 直接用 `file://` 打开不会走代理，会导致请求失败。

4. **VPN / 防火墙**
   - 某些 VPN / 安全软件可能拦截本地端口，请尝试关闭后重试。

### 2. "未加载到指定环境变量，请检查 .env 文件是否存在或变量名是否正确"

- 确认 `.env` 在 `backend` 目录；
- 确认变量名为 `DEEPSEEK_API_KEY`，无多余空格和引号；
- 文件扩展名不要是 `.txt`。

### 3. Node / npm 命令不可用

- 终端提示 `node`/`npm` 未找到：
  - 确认安装了 Node.js；
  - 确认 `C:\Program Files\nodejs\` 在 `Path` 中；
  - 重新打开终端再执行。

- PowerShell 提示执行策略错误：
  - 执行 `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`。

### 4. 分析时间很长，进度条卡在 80–90%

- 进度条是**按时间估算**的，最多走到约 90%，用来表示"接近完成"；
- 真正完成时机以后端返回为准，返回成功后进度条会补到 100%，并显示"分析完成"；
- 对于包含大量文章的 EPUB，整体处理时间可能在 5–15 分钟甚至更久，属正常现象；
- 可在运行 `uvicorn` 的终端中查看是否有持续日志输出，以判断是否仍在处理中。

---

## 七、建议的使用步骤

1. 双击 `start.bat` 一键启动（或按「四、启动方式」手动启动）；
2. 上传 EPUB 文件，点击「开始分析并生成 Word」；
3. 等待进度条接近完成，直到弹出"分析完成"提示；
4. 点击「下载 Word 文档」按钮获取结果。

---

## 八、部署到公网

如果您想将应用部署到公网，让其他人通过 URL 直接访问，请参考 `DEPLOY.md` 文件。

### 快速部署（单服务器）

1. **构建前端**
   ```bash
   cd frontend
   npm install
   npm run build
   ```

2. **配置后端环境变量**
   在 `backend` 目录创建 `.env` 文件，配置 `DEEPSEEK_API_KEY`

3. **启动服务**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **访问应用**
   打开浏览器访问 `http://your-server-ip:8000`

### Docker 部署

```bash
# 配置环境变量
export DEEPSEEK_API_KEY=sk-your-key

# 构建并运行
docker-compose up -d
```

详细部署说明请查看 `DEPLOY.md`。
