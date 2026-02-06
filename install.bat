@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo EPUB 分析助手 - 自动安装脚本
echo ========================================
echo.

echo [步骤 1/4] 检查系统环境...
echo.

REM 检查 Python
echo 检查 Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python
    echo.
    echo 请先安装 Python 3.10 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
python --version
echo Python 检查通过
echo.

REM 检查 Node.js
echo 检查 Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js
    echo.
    echo 请先安装 Node.js (LTS 版本)
    echo 下载地址: https://nodejs.org/
    echo.
    pause
    exit /b 1
)
node --version
echo Node.js 检查通过
echo.

echo [步骤 2/4] 安装 Python 依赖...
echo.
cd backend

REM 创建虚拟环境
if not exist ".venv" (
    echo 创建 Python 虚拟环境...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败
        cd ..
        pause
        exit /b 1
    )
)

REM 激活虚拟环境并安装依赖
echo 激活虚拟环境...
call .venv\Scripts\activate.bat

echo 安装 Python 依赖包（这可能需要几分钟）...
pip install --upgrade pip -q
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] Python 依赖安装失败
    cd ..
    pause
    exit /b 1
)
echo Python 依赖安装完成
echo.

cd ..

echo [步骤 3/4] 安装前端依赖...
echo.
cd frontend

if not exist "node_modules" (
    echo 安装前端依赖包（这可能需要几分钟）...
    call npm install
    if %errorlevel% neq 0 (
        echo [错误] 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
) else (
    echo 前端依赖已存在，跳过安装
)
echo 前端依赖检查完成
echo.

cd ..

echo [步骤 4/4] 配置环境变量...
echo.
cd backend

if not exist ".env" (
    echo 未找到 .env 文件，正在创建...
    echo.
    
    REM 检查是否有示例文件
    if exist "..\.env.example" (
        copy "..\.env.example" ".env" >nul
        echo 已从 .env.example 创建 .env 文件
    ) else (
        REM 创建基本的 .env 文件
        (
            echo DEEPSEEK_API_KEY=sk-your-api-key-here
            echo DEEPSEEK_API_BASE=https://api.deepseek.com
            echo DEEPSEEK_MODEL=deepseek-chat
        ) > .env
        echo 已创建 .env 文件模板
    )
    
    echo.
    echo ========================================
    echo 重要：请配置 API Key
    echo ========================================
    echo.
    echo 请编辑 backend\.env 文件，将 DEEPSEEK_API_KEY 的值
    echo 替换为您从 DeepSeek 获取的真实 API Key
    echo.
    echo 获取 API Key: https://platform.deepseek.com/
    echo.
    echo 按任意键打开 .env 文件进行编辑...
    pause >nul
    
    REM 尝试用默认编辑器打开
    notepad .env 2>nul
) else (
    echo .env 文件已存在
    echo 如需修改配置，请编辑 backend\.env 文件
)

cd ..

echo.
echo ========================================
echo 安装完成！
echo ========================================
echo.
echo 下一步：
echo 1. 确认已配置 backend\.env 文件中的 DEEPSEEK_API_KEY
echo 2. 双击 start.bat 启动应用
echo 3. 或手动运行：
echo    - 后端: cd backend ^&^& .venv\Scripts\activate ^&^& uvicorn main:app --reload --port 8000
echo    - 前端: cd frontend ^&^& npm run dev
echo.
pause
