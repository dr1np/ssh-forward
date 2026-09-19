"""Package locally built, self-contained V0.1 artifacts and checksums."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts")
    args = parser.parse_args()

    release = args.output / f"v{args.version}"
    portable = release / f"ssh-forwarder-v{args.version}-windows-x64"
    if portable.exists():
        shutil.rmtree(portable)
    portable.mkdir(parents=True)

    main_binary = ROOT / "frontend" / "src-tauri" / "target" / "release" / "ssh-forwarder.exe"
    sidecar_candidates = sorted(
        (ROOT / "frontend" / "src-tauri" / "binaries").glob("ssh-forwarder-service-*.exe")
    )
    if not main_binary.is_file():
        raise SystemExit(f"Missing release binary: {main_binary}")
    if len(sidecar_candidates) != 1:
        raise SystemExit(f"Expected one Windows sidecar, found {len(sidecar_candidates)}")

    shutil.copy2(main_binary, portable / "SSHForwarder.exe")
    shutil.copy2(sidecar_candidates[0], portable / "ssh-forwarder-service.exe")
    (portable / "README.txt").write_text(
        "SSH Forwarder v0.1.0\n\n"
        "Run SSHForwarder.exe. Windows OpenSSH Client and WebView2 are required.\n"
        "Close the window to keep forwarding in the system tray. Right-click the tray icon\n"
        "to show the window or exit and stop all forwarding.\n",
        encoding="utf-8",
    )

    archive = release / f"ssh-forwarder-v{args.version}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(portable.iterdir()):
            bundle.write(path, path.name)

    linux_appimage = next(
        (ROOT / "frontend" / "src-tauri" / "target" / "release" / "bundle" / "appimage").glob("*.AppImage"),
        None,
    )
    linux_deb = next(
        (ROOT / "frontend" / "src-tauri" / "target" / "release" / "bundle" / "deb").glob("*.deb"),
        None,
    )
    for source, name in (
        (linux_appimage, f"ssh-forwarder-v{args.version}-linux-x64.AppImage"),
        (linux_deb, f"ssh-forwarder-v{args.version}-linux-x64.deb"),
    ):
        if source and source.is_file():
            shutil.copy2(source, release / name)

    checksum_file = release / "SHA256SUMS.txt"
    files = sorted(path for path in release.rglob("*") if path.is_file() and path != checksum_file)
    checksum_file.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(release).as_posix()}\n" for path in files),
        encoding="ascii",
    )
    print(f"Packaged {archive}")
    print(f"Checksums {checksum_file}")


if __name__ == "__main__":
    main()
