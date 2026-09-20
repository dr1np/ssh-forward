# SSH Forwarder release notes

仓库早期的 `v0.1.0` 发布包使用 Python sidecar，`v0.2.0` 是 Rust 后端的首个单 exe 版本。当前界面优化版本为 `v0.2.1`；旧 tag 仍保留，便于复现历史包。

## Windows

在仓库根目录执行：

```powershell
cd frontend
npm ci
npm run desktop:build -- --no-bundle
cd ..
powershell -ExecutionPolicy Bypass -File scripts/package_release.ps1 -Version 0.2.1
```

脚本会把 `frontend/src-tauri/target/release/ssh-forwarder.exe` 复制为
`SSHForwarder.exe`，生成 portable zip 和 SHA-256 校验文件。portable 包不包含 service 程序，也不需要 Python。

## Linux

Linux x64 AppImage 和 deb 应在 Ubuntu 22.04/WebKitGTK/Rust/Node 工具链中构建：

```bash
cd frontend
npm ci
npm run desktop:build -- --no-bundle
npm run tauri build -- --config src-tauri/tauri.release.conf.json
```

Linux 运行时仍依赖主机 OpenSSH 和桌面 WebKit 运行库；应用本身不携带 Python。

## macOS

macOS 需要在 macOS 主机上运行相同的 Tauri 构建命令。当前工作流不负责签名和 notarization，正式分发前应使用项目自己的 Apple Developer 签名流程。
