# SSH Forwarder frontend

这是 SSH 端口转发助手的第一阶段 Svelte/Vite 前端壳。

当前版本使用显式标记的演示数据，暂未连接 Python 核心或 Tauri command。后续接入顺序：

1. Tauri bridge；
2. Python sidecar；
3. Rust core；
4. 移除 Python sidecar。

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

`npm run tauri dev` 需要 Windows 的 MSVC Rust toolchain、Visual Studio C++ Build Tools 和 WebView2。当前 Tauri 壳只加载 Svelte 演示界面，尚未接入 Python sidecar。

Tauri debug 构建：

```powershell
npm run tauri build -- --debug --no-bundle
```
