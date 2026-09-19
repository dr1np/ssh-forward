# SSH Forwarder frontend

这是 SSH 端口转发助手的 Svelte/Vite + Tauri 前端。浏览器预览使用演示数据，Tauri 运行时会通过 Rust bridge 启动 JSONL sidecar，并连接现有 SSH 核心。

桌面版支持关闭窗口后收纳到系统托盘。右键托盘图标可以显示窗口，或退出并停止所有转发；偏好设置可以关闭收纳行为。

浏览器预览仍使用显式标记的演示数据；Tauri debug 运行时已经接入 Python 核心。后续迁移顺序：

1. 完善 Python sidecar 打包和跨平台启动；
2. 将核心模块迁移到 Rust；
3. 移除 Python sidecar。

## 本地开发

```powershell
npm install
npm run dev
```

## 检查与构建

```powershell
npm run check
npm run build
npm run tauri dev
```

`npm run tauri dev` 需要 Windows 的 MSVC Rust toolchain、Visual Studio C++ Build Tools 和 WebView2。开发模式启动 `python -m ssh_forwarder.service`；正式版会把 PyInstaller sidecar 放入 Tauri 资源目录，不依赖用户安装 Python。

Tauri debug 构建：

```powershell
npm run tauri build -- --debug --no-bundle
```

V0.1 Windows portable 构建从仓库根目录执行：

```powershell
uv venv .venv --python 3.13
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
$env:PATH = "C:\Project\SSHforward\.venv\Scripts;C:\Users\tanzi\.cargo\bin;" + $env:PATH
cd frontend
npm run desktop:build -- --no-bundle
cd ..
.venv/Scripts/python.exe scripts/package_release.py --version 0.1.0
```
