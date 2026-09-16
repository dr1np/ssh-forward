from __future__ import annotations

import os
import queue
import shutil
import socket
import subprocess
import threading
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .models import ActiveTunnel, ForwardProfile


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_ssh_executable() -> str | None:
    return shutil.which("ssh.exe") or shutil.which("ssh")


def _format_host(host: str) -> str:
    value = host.strip()
    if ":" in value and not (value.startswith("[") and value.endswith("]")):
        return f"[{value}]"
    return value


def build_ssh_command(ssh_executable: str, profile: ForwardProfile) -> list[str]:
    profile.validate()
    forward_spec = (
        f"{_format_host(profile.local_bind)}:{profile.local_port}:"
        f"{_format_host(profile.remote_host)}:{profile.remote_port}"
    )
    command = [
        ssh_executable,
        "-N",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "ConnectTimeout=10",
        "-L",
        forward_spec,
    ]
    if profile.connection_type == "custom":
        command.extend(["-p", str(profile.ssh_port)])
        if profile.identity_file.strip():
            command.extend(["-i", str(Path(profile.identity_file).expanduser())])
    command.append(profile.ssh_destination)
    return command


def is_local_port_available(bind_address: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in bind_address else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        sock.bind((bind_address, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def find_available_port(bind_address: str = "127.0.0.1") -> int:
    family = socket.AF_INET6 if ":" in bind_address else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.bind((bind_address, 0))
        return int(sock.getsockname()[1])


class TunnelManager:
    def __init__(self, ssh_executable: str | None = None) -> None:
        self.ssh_executable = ssh_executable or find_ssh_executable()
        self.tunnels: dict[str, ActiveTunnel] = {}
        self.events: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self._lock = threading.RLock()
        self._accepting_starts = True

    def start(self, profile: ForwardProfile) -> ActiveTunnel:
        if not self.ssh_executable:
            raise RuntimeError(
                "未找到 Windows OpenSSH 客户端。请在“可选功能”中安装 OpenSSH 客户端。"
            )
        with self._lock:
            if not self._accepting_starts:
                raise RuntimeError("应用正在关闭，无法启动新的转发。")
            profile.validate()
            if not is_local_port_available(profile.local_bind, profile.local_port):
                raise RuntimeError(
                    f"本地端口 {profile.local_bind}:{profile.local_port} 已被占用。"
                )
            command = build_ssh_command(self.ssh_executable, profile)
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except OSError as exc:
                raise RuntimeError(f"无法启动 SSH：{exc}") from exc

            tunnel_id = uuid4().hex
            active = ActiveTunnel(tunnel_id, profile.clone(keep_id=False), process)
            self.tunnels[tunnel_id] = active
            threading.Thread(
                target=self._watch_process, args=(active,), daemon=True
            ).start()
            return active

    def _watch_process(self, tunnel: ActiveTunnel) -> None:
        messages: list[str] = []
        stderr = tunnel.process.stderr
        try:
            if stderr is not None:
                for line in iter(stderr.readline, ""):
                    clean = line.strip()
                    if clean:
                        messages.append(clean)
                        self.events.put(("log", tunnel.id, clean))
        except (OSError, ValueError) as exc:
            message = f"读取 SSH 错误日志失败：{exc}"
            messages.append(message)
            self.events.put(("log", tunnel.id, message))
        finally:
            if stderr is not None:
                try:
                    stderr.close()
                except (OSError, ValueError) as exc:
                    message = f"关闭 SSH 错误日志失败：{exc}"
                    messages.append(message)
                    self.events.put(("log", tunnel.id, message))
        return_code = tunnel.process.wait()
        ended_at = datetime.now()
        with self._lock:
            current = self.tunnels.get(tunnel.id)
            if current is None:
                return
            if current.ended_at is None:
                current.ended_at = ended_at
            if current.status == "正在停止":
                current.status = "已停止"
                self.events.put(("stopped", tunnel.id, "转发已停止"))
            else:
                current.status = "连接失败" if return_code else "已结束"
                current.last_error = messages[-1] if messages else f"SSH 已退出（代码 {return_code}）"
                self.events.put(("exited", tunnel.id, current.last_error))

    def get(self, tunnel_id: str) -> ActiveTunnel | None:
        with self._lock:
            return self.tunnels.get(tunnel_id)

    def snapshot(self) -> list[ActiveTunnel]:
        """Return a stable list for UI reads while workers update the registry."""

        with self._lock:
            return list(self.tunnels.values())

    def mark_connected_if_running(self, tunnel_id: str) -> bool:
        with self._lock:
            tunnel = self.tunnels.get(tunnel_id)
            if tunnel and tunnel.process.poll() is None:
                tunnel.status = "运行中"
                return True
            return False

    def stop(self, tunnel_id: str) -> None:
        with self._lock:
            tunnel = self.tunnels.get(tunnel_id)
            if not tunnel:
                return
            process = tunnel.process
            if process.poll() is not None:
                if tunnel.ended_at is None:
                    tunnel.ended_at = datetime.now()
                return
            previous_status = tunnel.status
            tunnel.status = "正在停止"

        try:
            process.terminate()
        except OSError:
            if process.poll() is not None:
                self._mark_ended_at(tunnel)
                return
            self._restore_status_if_running(tunnel, previous_status)
            raise
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError as exc:
                if process.poll() is None:
                    self._restore_status_if_running(tunnel, previous_status)
                    raise RuntimeError("无法终止 SSH 进程。") from exc
            try:
                process.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError) as exc:
                if process.poll() is None:
                    self._restore_status_if_running(tunnel, previous_status)
                    if isinstance(exc, subprocess.TimeoutExpired):
                        raise RuntimeError("SSH 进程未能在超时后停止。") from exc
                    raise RuntimeError("无法确认 SSH 进程已停止。") from exc
        except OSError:
            if process.poll() is None:
                self._restore_status_if_running(tunnel, previous_status)
                raise
        self._mark_ended_at(tunnel)

    def _mark_ended_at(self, tunnel: ActiveTunnel) -> None:
        with self._lock:
            current = self.tunnels.get(tunnel.id)
            if current is tunnel and current.ended_at is None:
                current.ended_at = datetime.now()

    def _restore_status_if_running(self, tunnel: ActiveTunnel, status: str) -> None:
        with self._lock:
            current = self.tunnels.get(tunnel.id)
            if (
                current is tunnel
                and current.process.poll() is None
                and current.status == "正在停止"
            ):
                current.status = status

    def remove_finished(self, tunnel_id: str) -> None:
        with self._lock:
            tunnel = self.tunnels.get(tunnel_id)
            if tunnel and tunnel.process.poll() is not None:
                self.tunnels.pop(tunnel_id, None)

    def _stop_ids(self, ids: Iterable[str]) -> list[tuple[str, str]]:
        errors: list[tuple[str, str]] = []
        for tunnel_id in ids:
            try:
                self.stop(tunnel_id)
            except Exception as exc:  # keep shutdown attempting every process
                errors.append((tunnel_id, str(exc)))
        return errors

    def stop_all(self) -> list[tuple[str, str]]:
        with self._lock:
            ids: Iterable[str] = list(self.tunnels)
        return self._stop_ids(ids)

    def shutdown(self) -> list[tuple[str, str]]:
        """Prevent new starts, then stop every tunnel known at shutdown time."""

        with self._lock:
            self._accepting_starts = False
            ids: Iterable[str] = list(self.tunnels)
        return self._stop_ids(ids)

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for item in self.tunnels.values() if item.process.poll() is None)
