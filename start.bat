@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在启动后端...
start "Backend" /d "%~dp0backend" cmd /k "(if exist .venv\Scripts\activate.bat (call .venv\Scripts\activate.bat)) && uvicorn main:app --reload --port 8000"

echo 正在启动前端...
start "Frontend" /d "%~dp0frontend" cmd /k "npm run dev"

echo 等待服务启动...
timeout /t 5 /nobreak >nul

echo 正在打开浏览器...
start http://localhost:5173

echo.
echo 后端和前端已启动，两个 CMD 窗口将保持打开。
echo 关闭服务时，请分别在对应窗口中按 Ctrl+C 或直接关闭窗口。
pause
