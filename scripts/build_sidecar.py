"""Build a native sidecar and verify its JSONL protocol before bundling."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    version = subprocess.check_output(["rustc", "-vV"], text=True)
    target = next(line.split(": ", 1)[1] for line in version.splitlines() if line.startswith("host:"))
    name = "ssh-forwarder-service"
    extension = ".exe" if sys.platform == "win32" else ""
    output = ROOT / "build" / "sidecar-dist"
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--name", name, "--paths", str(ROOT),
        "--distpath", str(output), "--workpath", str(ROOT / "build" / "sidecar-work"),
        "--specpath", str(ROOT / "build"), str(ROOT / "scripts" / "service_entry.py"),
    ], cwd=ROOT, check=True)
    binary = output / (name + extension)
    with tempfile.TemporaryDirectory() as temporary:
        env = dict(os.environ, SSH_FORWARDER_DATA_DIR=temporary)
        result = subprocess.run([str(binary)], input=json.dumps({"id": "smoke", "method": "get_status"}) + "\n",
                                text=True, capture_output=True, env=env, cwd=temporary, timeout=30, check=True)
        reply = json.loads(result.stdout)
        if reply.get("ok") is not True or reply.get("id") != "smoke":
            raise RuntimeError(f"Sidecar smoke test failed: {reply}")
    destination = ROOT / "frontend" / "src-tauri" / "binaries" / f"{name}-{target}{extension}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, destination)
    print(f"Verified native sidecar: {destination}")


if __name__ == "__main__":
    main()
