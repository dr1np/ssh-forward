@echo off
cd /d "%~dp0"

if not exist "frontend\node_modules" (
    echo 未找到前端依赖，请先在 frontend 目录运行 npm ci。
    pause
    exit /b 1
)

pushd frontend
npm run tauri dev
set "EXITCODE=%ERRORLEVEL%"
popd
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
pause
exit /b 1
