# SSH Forwarder frontend

这是 SSH 端口转发助手的 Svelte/Vite + Tauri 前端。浏览器预览使用演示数据，Tauri debug 运行时会通过 Rust bridge 启动仓库内的 Python JSONL service，并连接现有 SSH 核心。

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

`npm run tauri dev` 需要 Windows 的 MSVC Rust toolchain、Visual Studio C++ Build Tools 和 WebView2。Tauri debug 运行时会启动 `python -m ssh_forwarder.service`；正式发布前仍需把它打包为跨平台 sidecar。

Tauri debug 构建：

```powershell
npm run tauri build -- --debug --no-bundle
```
