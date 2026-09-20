@echo off
cd /d "%~dp0"

set "APP=%~dp0SSHForwarder.exe"
if exist "%APP%" (
    start "" "%APP%"
    exit /b 0
)

set "APP=%~dp0frontend\src-tauri\target\release\ssh-forwarder.exe"
if exist "%APP%" (
    start "" "%APP%"
    exit /b 0
)

echo 未找到 SSHForwarder.exe。请先按 README.md 中的说明构建桌面程序。
pause
exit /b 1
