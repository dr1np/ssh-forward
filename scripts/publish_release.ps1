<#
Publishes the v0.1.0 GitHub release with the Windows x64 artifacts.
The token is read from Git Credential Manager and never written to disk.
#>
param(
    [string]$Repository = "dr1np/ssh-forward",
    [string]$Tag = "v0.1.0",
    [string]$ArtifactDirectory = "artifacts/v0.1.0"
)

$ErrorActionPreference = "Stop"

$credentialInput = "protocol=https`nhost=github.com`n`n"
$credential = $credentialInput | git credential-manager get 2>$null
$token = ($credential | Where-Object { $_ -match "^password=" }) -replace "^password=", ""
if (-not $token) { throw "无法从 Git Credential Manager 读取 GitHub 凭据。" }

$headers = @{
    Authorization          = "Bearer $token"
    Accept                 = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$notes = @"
SSH Forwarder v0.1.0

面向 Windows、Linux 的 SSH 本地端口转发桌面工具。直接调用系统 OpenSSH，不保存密码。

## Windows x64

下载 `ssh-forwarder-v0.1.0-windows-x64.zip` 并解压后运行 `SSHForwarder.exe`。程序自带后端 sidecar，
无需安装 Python；需要 Windows 10/11、WebView2 和 Windows OpenSSH 客户端。

- 关闭窗口收纳到系统托盘并保持转发。
- 右键托盘图标可显示主窗口，或退出并停止全部转发。
- 偏好设置可关闭收纳行为，改为退出前确认。

## Linux x64

仓库同时包含本地构建的 AppImage 与 deb 包，需要系统 OpenSSH 和 WebKitGTK 桌面环境。

## macOS

本版本未提供 macOS 二进制：构建主机为 Windows，缺少 macOS 原生工具链。

## 校验

`SHA256SUMS.txt` 中包含各产物的 SHA256 校验值。

## 已知限制

本版本未做代码签名，Windows SmartScreen / macOS Gatekeeper 可能提示来自未知发布者。
"@

$releasePayload = @{
    tag_name         = $Tag
    name             = $Tag
    body             = $notes
    draft            = $false
    prerelease       = $false
    generate_release_notes = $false
} | ConvertTo-Json -Depth 5

$payloadFile = Join-Path ([System.IO.Path]::GetTempPath()) "ssh-forwarder-release-$Tag.json"
[System.IO.File]::WriteAllText($payloadFile, $releasePayload, [System.Text.UTF8Encoding]::new($false))

$existing = curl.exe -s -H "Authorization: Bearer $token" "https://api.github.com/repos/$Repository/releases/tags/$Tag"
$existingRelease = $null
try { $existingRelease = $existing | ConvertFrom-Json } catch { }

if ($existingRelease -and $existingRelease.id) {
    Write-Output "Release $Tag 已存在（id=$($existingRelease.id)），更新说明。"
    $null = curl.exe -s -X PATCH -H "Authorization: Bearer $token" -H "Accept: application/vnd.github+json" `
        "https://api.github.com/repos/$Repository/releases/$($existingRelease.id)" `
        --data-binary "@$payloadFile"
    $releaseId = $existingRelease.id
} else {
    $created = curl.exe -s -X POST -H "Authorization: Bearer $token" -H "Accept: application/vnd.github+json" `
        -H "Content-Type: application/json" `
        "https://api.github.com/repos/$Repository/releases" --data-binary "@$payloadFile"
    $release = $created | ConvertFrom-Json
    if (-not $release.id) { throw "创建 Release 失败：$created" }
    Write-Output "已创建 Release $Tag（id=$($release.id)）。"
    $releaseId = $release.id
}

$uploadUrl = "https://uploads.github.com/repos/$Repository/releases/$releaseId/assets"

$portableDirectory = Join-Path $ArtifactDirectory "ssh-forwarder-v0.1.0-windows-x64"
$assets = @(
    @{ Path = Join-Path $portableDirectory "SSHForwarder.exe"; Name = "SSHForwarder.exe"; Type = "application/vnd.microsoft.portable-executable" },
    @{ Path = Join-Path $portableDirectory "ssh-forwarder-service.exe"; Name = "ssh-forwarder-service.exe"; Type = "application/vnd.microsoft.portable-executable" },
    @{ Path = Join-Path $ArtifactDirectory "ssh-forwarder-v0.1.0-windows-x64.zip"; Name = "ssh-forwarder-v0.1.0-windows-x64.zip"; Type = "application/zip" },
    @{ Path = Join-Path $ArtifactDirectory "SHA256SUMS.txt"; Name = "SHA256SUMS.txt"; Type = "text/plain" }
)

$existingAssets = @()
$assetListJson = curl.exe -sS -H "Authorization: Bearer $token" "https://api.github.com/repos/$Repository/releases/$releaseId/assets"
if ($assetListJson) { $existingAssets = ($assetListJson | ConvertFrom-Json) }

foreach ($asset in $assets) {
    if (-not (Test-Path -LiteralPath $asset.Path)) { Write-Warning "跳过缺失文件：$($asset.Path)"; continue }
    $already = $existingAssets | Where-Object { $_.name -eq $asset.Name }
    if ($already) {
        Write-Output "$($asset.Name) 已存在（$($already.size) 字节），跳过。"
        continue
    }
    Write-Output "上传 $($asset.Name)..."
    $apiUrl = "$uploadUrl`?name=$($asset.Name)"
    $response = curl.exe -sS -w "|HTTP=%{http_code}" -X POST -H "Authorization: Bearer $token" -H "Accept: application/vnd.github+json" -H "Content-Type: $($asset.Type)" $apiUrl --data-binary "@$($asset.Path)"
    if ($response -match "browser_download_url`":`"([^`"]+)") {
        Write-Output "  上传完成：$($Matches[1])"
    } else {
        Write-Warning "  上传失败：$response"
    }
}

$token = $null
$credential = $null
Remove-Item -LiteralPath $payloadFile -Force -ErrorAction SilentlyContinue
Write-Output "完成：https://github.com/$Repository/releases/tag/$Tag"
