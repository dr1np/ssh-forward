@echo off
cd /d "%~dp0"

where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 main.py
    exit /b 0
)

where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw main.py
    exit /b 0
)

echo 未找到 Python。请先安装 Python 3.10 或更高版本，并勾选 Add Python to PATH。
pause
exit /b 1

