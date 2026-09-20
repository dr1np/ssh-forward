# SSH 端口转发助手

一个跨平台桌面工具，用来集中管理 SSH 本地端口转发。它直接调用系统 OpenSSH，不保存账号密码。

## 能做什么

- 自动读取 `%USERPROFILE%\.ssh\config` 中的具体 `Host` 别名，并支持 `Include` 配置。
- 也可直接填写 IP / 域名、SSH 端口、用户名和私钥。
- 同时运行多条本地转发，随时停止、复制本地地址或更换本地端口。
- 收藏常用配置，双击即可启动。
- 自动寻找空闲本地端口。
- 支持仅本机监听（`127.0.0.1` / `::1`）和局域网监听（`0.0.0.0`，启动前会警告）。
- SSH 连接失败时在界面中显示原始错误日志。

## 运行环境

Windows 发行包自带 Python sidecar，因此用户只需要 Windows 10/11、WebView2 和 Windows OpenSSH 客户端。Windows 11 通常已自带 OpenSSH；如果界面提示未找到，请前往“设置 → 系统 → 可选功能”安装 **OpenSSH 客户端**。

从源码运行 Python service 或旧版 Tk 界面时，需要 Python 3.10 或更高版本。

## 启动

双击 [`启动SSH端口转发助手.bat`](./启动SSH端口转发助手.bat) 即可无控制台启动。

如果需要查看 Python 自身的报错，可双击 [`调试运行.bat`](./调试运行.bat)，或在项目目录运行：

```powershell
python main.py
```

## Tauri 桌面版与系统托盘

正式桌面版位于 [`frontend/`](./frontend/)，使用 Svelte/Vite + Tauri。关闭窗口会收纳到系统托盘并保持转发，右键托盘图标可以显示主窗口，或退出并停止所有转发。偏好设置可以关闭这一行为，改为直接退出确认。

浏览器预览使用显式标记的演示数据；Tauri 开发运行时通过 Rust bridge 启动仓库内 Python service。旧版 Tk 界面和源码 service 仍保留用于兼容与测试。

```powershell
cd frontend
npm install
npm run dev
```

安装 Rust、Visual Studio C++ Build Tools 和 WebView2 后，可运行桌面壳：

```powershell
npm run tauri dev
```

检查和生产构建：

```powershell
npm run check
npm run build
```

从仓库根目录准备 Windows V0.1 portable 包（以下命令中的 `$PWD` 指仓库根目录）：

```powershell
uv venv .venv --python 3.13
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
$env:PATH = "$PWD\.venv\Scripts;$env:USERPROFILE\.cargo\bin;" + $env:PATH
cd frontend
npm run desktop:build -- --no-bundle
cd ..
.venv/Scripts/python.exe scripts/package_release.py --version 0.1.0
```

构建记录和平台限制见 [`docs/release-v0.1.md`](docs/release-v0.1.md)。Linux 需要 WebKitGTK 和系统 OpenSSH；macOS 需要 WebKit、系统 OpenSSH，当前本地包未签名。

## 使用方法

1. 在左侧选择 **SSH Config** 主机，或切换到 **自定义主机** 填写连接信息。
2. 填写本地监听端口和 SSH 服务器一侧可以访问的目标地址、目标端口。
3. 点击 **启动转发**。成功后，本地应用连接界面所示的 `localhost:端口` 即可。
4. 选中运行中的转发，可以复制地址、停止，或更换本地端口（工具会自动重启该 SSH 通道）。
5. 点击 **保存收藏**，之后可在收藏页双击快速启动。

例如，通过 SSH 主机 `production` 访问服务器本机的 PostgreSQL：

| 配置项 | 示例 |
| --- | --- |
| SSH Config 主机 | `production` |
| 本地端口 | `15432` |
| 目标主机 | `127.0.0.1` |
| 目标端口 | `5432` |

然后让本地数据库客户端连接 `localhost:15432`。

## 认证与安全

- 工具采用非交互认证，不会弹窗索取或保存 SSH 密码。请提前配置 SSH 密钥，或把密钥加入 `ssh-agent`。
- 首次连接的新主机会采用 OpenSSH 的 `accept-new` 策略记录主机指纹；已记录主机的指纹发生变化时仍会拒绝连接。
- 默认只监听 `127.0.0.1`，外部设备不能直接访问。仅在确有需要时选择 `0.0.0.0`，并同时检查 Windows 防火墙规则。
- 收藏保存在 `%APPDATA%\SSHForwarder\settings.json`。其中只包含主机、端口和私钥路径等配置，不包含私钥内容或密码。

## 测试

```powershell
python -m unittest discover -s tests -v
```
