param(
    [string]$Version = "0.2.2",
    [string]$Output = (Join-Path $PSScriptRoot "..\artifacts")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRoot = [System.IO.Path]::GetFullPath($Output)
$release = Join-Path $outputRoot ("v" + $Version)
New-Item -ItemType Directory -Path $release -Force | Out-Null
$portable = Join-Path $release ("ssh-forwarder-v" + $Version + "-windows-x64")
$mainBinary = Join-Path $root "frontend\src-tauri\target\release\ssh-forwarder.exe"

if (Test-Path -LiteralPath $portable) {
    Remove-Item -LiteralPath $portable -Recurse -Force
}
New-Item -ItemType Directory -Path $portable -Force | Out-Null
if (-not (Test-Path -LiteralPath $mainBinary -PathType Leaf)) {
    throw "Missing release binary: $mainBinary"
}

Copy-Item -LiteralPath $mainBinary -Destination (Join-Path $portable "SSHForwarder.exe")
@"
SSH Forwarder v$Version

Run SSHForwarder.exe. Windows OpenSSH Client and WebView2 are required.
Close the window to keep forwarding in the system tray. Right-click the tray icon
to show the window or exit and stop all forwarding.
This package contains one executable; Python and a separate service process are not required.
"@ | Set-Content -LiteralPath (Join-Path $portable "README.txt") -Encoding utf8

$archive = Join-Path $release ("ssh-forwarder-v" + $Version + "-windows-x64.zip")
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -Path (Join-Path $portable "*") -DestinationPath $archive -CompressionLevel Optimal

$oldLinuxAssets = Get-ChildItem -LiteralPath $release -File -Filter ("ssh-forwarder-v" + $Version + "-linux-x64.*") -ErrorAction SilentlyContinue
if ($oldLinuxAssets) {
    $oldLinuxAssets | Remove-Item -Force
}
$appImage = Get-ChildItem -LiteralPath (Join-Path $root "frontend\src-tauri\target\release\bundle\appimage") -Filter ("*_" + $Version + "_*.AppImage") -File -ErrorAction SilentlyContinue | Select-Object -First 1
$deb = Get-ChildItem -LiteralPath (Join-Path $root "frontend\src-tauri\target\release\bundle\deb") -Filter ("*_" + $Version + "_*.deb") -File -ErrorAction SilentlyContinue | Select-Object -First 1
if ($appImage) {
    Copy-Item -LiteralPath $appImage.FullName -Destination (Join-Path $release ("ssh-forwarder-v" + $Version + "-linux-x64.AppImage")) -Force
}
if ($deb) {
    Copy-Item -LiteralPath $deb.FullName -Destination (Join-Path $release ("ssh-forwarder-v" + $Version + "-linux-x64.deb")) -Force
}

$checksum = Join-Path $release "SHA256SUMS.txt"
$lines = Get-ChildItem -LiteralPath $release -File -Recurse |
    Where-Object { $_.FullName -ne (Resolve-Path $checksum -ErrorAction SilentlyContinue).Path } |
    Sort-Object FullName |
    ForEach-Object {
        $relative = $_.FullName.Substring($release.Length + 1).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $relative"
    }
$lines | Set-Content -LiteralPath $checksum -Encoding ascii
Write-Host "Packaged $archive"
Write-Host "Checksums $checksum"
