# SSH Forwarder frontend

这是 SSH 端口转发助手的 Svelte/Vite + Tauri 前端。浏览器预览使用明确标记的演示数据，Tauri 运行时直接调用同一个 Rust 后端核心；桌面包只有一个可执行文件，不启动 Python service 或 sidecar。

## 本地开发

```powershell
npm ci
npm run dev
```

`npm run tauri dev` 需要 MSVC Rust toolchain、Visual Studio C++ Build Tools、WebView2 和系统 OpenSSH。生产构建使用：

```powershell
npm run check
npm run build
npm run desktop:build -- --no-bundle
```

关闭窗口时，应用会按偏好设置收进系统托盘并保持转发；从托盘退出会请求 Rust 后端停止所有 SSH 子进程。
