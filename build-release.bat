@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo EPUB 分析助手 - 发布包构建脚本
echo ========================================
echo.

set RELEASE_DIR=epub-analyst-release

echo [1/5] 清理旧的发布目录...
if exist "%RELEASE_DIR%" (
    echo 删除旧目录: %RELEASE_DIR%
    rmdir /s /q "%RELEASE_DIR%"
)
echo 完成
echo.

echo [2/5] 检查 Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Node.js，请先安装 Node.js
    pause
    exit /b 1
)
echo Node.js 版本:
node --version
echo.

echo [3/5] 构建前端...
cd frontend
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
    if %errorlevel% neq 0 (
        echo 错误: 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
)
echo 构建前端应用...
call npm run build
if %errorlevel% neq 0 (
    echo 错误: 前端构建失败
    cd ..
    pause
    exit /b 1
)
if not exist "dist" (
    echo 错误: 前端构建失败，未找到 dist 目录
    cd ..
    pause
    exit /b 1
)
cd ..
echo 前端构建完成
echo.

echo [4/5] 创建发布目录结构...
mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\backend"
mkdir "%RELEASE_DIR%\frontend-dist"

echo 复制后端文件...
xcopy /E /I /Y backend\*.py "%RELEASE_DIR%\backend\" >nul
xcopy /E /I /Y backend\requirements.txt "%RELEASE_DIR%\backend\" >nul
if exist "backend\.env.example" (
    copy /Y "backend\.env.example" "%RELEASE_DIR%\backend\" >nul
)

echo 复制前端构建产物...
xcopy /E /I /Y frontend\dist\* "%RELEASE_DIR%\frontend-dist\" >nul

echo 复制配置文件...
copy /Y "README-USER.md" "%RELEASE_DIR%\" >nul 2>&1
copy /Y ".env.example" "%RELEASE_DIR%\" >nul 2>&1
copy /Y "install.bat" "%RELEASE_DIR%\" >nul 2>&1
if exist "backend\.env.example" (
    copy /Y "backend\.env.example" "%RELEASE_DIR%\backend\" >nul
)
echo 完成
echo.

echo [5/5] 创建启动脚本...
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%%~dp0"
echo.
echo echo 检查前端构建...
echo if not exist "frontend-dist" ^(
echo     echo 错误: 前端构建文件不存在
echo     pause
echo     exit /b 1
echo ^)
echo.
echo echo 启动后端服务...
echo cd backend
echo if not exist ".venv" ^(
echo     echo 创建虚拟环境...
echo     python -m venv .venv
echo ^)
echo.
echo call .venv\Scripts\activate.bat
echo.
echo echo 检查依赖...
echo pip install -q -r requirements.txt
echo.
echo if not exist ".env" ^(
echo     echo.
echo     echo 警告: 未找到 .env 文件
echo     echo 请创建 backend\.env 文件并配置 DEEPSEEK_API_KEY
echo     echo.
echo     pause
echo ^)
echo.
echo echo.
echo echo 启动服务...
echo echo 访问地址: http://localhost:8000
echo echo.
echo uvicorn main:app --host 0.0.0.0 --port 8000
echo.
echo pause
) > "%RELEASE_DIR%\start.bat"

echo 完成
echo.

echo ========================================
echo 构建完成！
echo ========================================
echo.
echo 发布目录: %RELEASE_DIR%
echo.
echo 下一步:
echo 1. 检查 %RELEASE_DIR% 目录中的文件
echo 2. 将整个目录打包成 ZIP 文件
echo 3. 分发给用户
echo.
pause
