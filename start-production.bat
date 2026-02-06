@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 检查前端构建...
if not exist "frontend\dist" (
    echo 前端未构建，正在构建...
    cd frontend
    call npm run build
    cd ..
    if not exist "frontend\dist" (
        echo 错误: 前端构建失败
        pause
        exit /b 1
    )
)

echo 启动后端服务...
cd backend
if not exist ".venv" (
    echo 创建虚拟环境...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo 检查依赖...
pip install -q -r requirements.txt

if not exist ".env" (
    echo.
    echo 警告: 未找到 .env 文件
    echo 请创建 backend\.env 文件并配置 DEEPSEEK_API_KEY
    echo.
    pause
)

echo.
echo 启动服务...
echo 访问地址: http://localhost:8000
echo.
uvicorn main:app --host 0.0.0.0 --port 8000

pause
