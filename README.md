# SSH 端口转发助手

一个跨平台桌面工具，用来集中管理 SSH 本地端口转发。桌面后端完全由 Rust 实现，直接调用系统 OpenSSH，不保存账号密码，也不需要 Python 或独立 service 可执行文件。

## 功能

- 自动读取 SSH config 中的具体 `Host` 别名，支持 `Include`、通配 Include、引号、环境变量和循环保护。
- 也可以直接填写 IP 或域名、SSH 端口、用户名和私钥路径。
- 同时运行多条本地转发，支持停止、复制本地地址和无损更换本地端口。
- 收藏常用配置，双击即可启动。
- 自动寻找空闲本地端口。
- 支持 `127.0.0.1`、`::1` 和 `0.0.0.0` 监听；选择局域网监听时会先提示风险。
- SSH 失败时在界面日志中显示错误输出，并保留失败记录供重试或清理。

## 运行环境

发行包只包含一个 Tauri 桌面可执行文件。运行时需要：

- Windows 10/11、WebView2 和 Windows OpenSSH Client；
- Linux 的 WebKitGTK、桌面运行库和系统 OpenSSH；
- macOS 的 WebKit、系统 OpenSSH。

OpenSSH 可执行文件必须位于系统 `PATH` 中。收藏保存在 Windows 的 `%APPDATA%\\SSHForwarder\\settings.json`，Linux 的 `$XDG_CONFIG_HOME/SSHForwarder/settings.json`，macOS 的 `~/Library/Application Support/SSHForwarder/settings.json`。

## 开发与检查

```powershell
cd frontend
npm ci
npm run check
npm run build
npm run tauri dev
```

Rust 后端测试：

```powershell
cargo test --manifest-path frontend/src-tauri/Cargo.toml
cargo test --manifest-path frontend/src-tauri/Cargo.toml --features test-helper --test runtime_integration
```

第二条命令启动仓库内的 Rust 假 SSH 进程，覆盖启动、就绪、错误、停止、端口冲突和端口切换，不依赖 Python。

## 构建与打包

Windows 本地构建：

```powershell
cd frontend
npm run desktop:build -- --no-bundle
cd ..
powershell -ExecutionPolicy Bypass -File scripts/package_release.ps1 -Version 0.2.2
```

构建结果位于 `artifacts/v0.2.2/`。Windows portable 压缩包内只有 `SSHForwarder.exe` 和使用说明，不再有 `ssh-forwarder-service.exe`。Linux 的 AppImage/deb 可以使用 `scripts/Dockerfile.linux` 中的工具链构建；macOS 需要在 macOS 主机上运行相同的 Tauri 构建命令。

## 使用

1. 在左侧选择 SSH Config 主机，或切换到自定义主机填写连接信息。
2. 填写本地监听端口、远端目标地址和目标端口。
3. 点击“启动转发”。连接建立后，使用界面显示的本地地址连接。
4. 选中运行中的转发，可以复制地址、停止或更换本地端口。更换端口会先确认新通道就绪，再停止旧通道。
5. 点击“保存收藏”，之后可以从收藏页快速启动。

工具使用 `BatchMode=yes`，不会弹窗索取或保存 SSH 密码。请预先配置 SSH 密钥或 ssh-agent。首次连接的新主机会使用 `accept-new` 记录主机指纹；已有主机的指纹变化仍会被拒绝。
