# SSH Forwarder v0.1 release record

This release record describes how the v0.1.0 artifacts were built.

## Windows

The Windows x64 portable package contains the Tauri desktop executable and a
PyInstaller sidecar. It requires the Windows OpenSSH Client and WebView2. The
application starts with its main window visible; closing the window places it in
the system tray while forwarding continues. The tray menu can show the window
or exit and stop every forwarding process.

Build and package from the repository root:

```powershell
uv venv .venv --python 3.13
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
$env:PATH = "$PWD\.venv\Scripts;$env:USERPROFILE\.cargo\bin;" + $env:PATH
cd frontend
npm run desktop:build -- --no-bundle
cd ..
.venv/Scripts/python.exe scripts/package_release.py --version 0.1.0
```

The package and `SHA256SUMS.txt` are written under `artifacts/v0.1.0/`.

## Linux

Linux x64 AppImage and deb bundles were built locally in Docker using Ubuntu
22.04, WebKitGTK, Rust, Node 22 and a Linux PyInstaller sidecar. They are
available under `artifacts/v0.1.0/` as `ssh-forwarder-v0.1.0-linux-x64.AppImage`
and `ssh-forwarder-v0.1.0-linux-x64.deb`. Linux users need system OpenSSH;
the deb/AppImage carries the application sidecar and WebKit runtime libraries
but still relies on the host desktop stack.

## macOS

macOS cannot be compiled natively from this Windows host. Build that target on
a native macOS runner with the same commands, using the platform Python and
Rust target; the sidecar must be rebuilt for each target triple.

The macOS output is unsigned in this local workflow and will require the usual
Gatekeeper approval or signing/notarization before broad distribution.
