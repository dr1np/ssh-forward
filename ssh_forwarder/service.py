"""JSON Lines bridge used by the first Tauri migration stage."""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
from datetime import datetime
from typing import Any
from pathlib import Path

from .models import ActiveTunnel, ForwardProfile
from .ssh_config import discover_ssh_hosts
from .storage import ProfileStore
from .tunnel_manager import TunnelManager, find_available_port


def _status_value(tunnel: ActiveTunnel) -> str:
    return {
        "正在连接": "connecting",
        "运行中": "running",
        "正在停止": "stopping",
        "已停止": "stopped",
        "连接失败": "failed",
        "已结束": "stopped",
    }.get(tunnel.status, "failed")


def _elapsed(tunnel: ActiveTunnel) -> str:
    end = tunnel.ended_at or datetime.now()
    seconds = max(0, int((end - tunnel.started_at).total_seconds()))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _serialize_profile(profile: ForwardProfile) -> dict[str, Any]:
    return profile.to_dict()


def _serialize_tunnel(tunnel: ActiveTunnel) -> dict[str, Any]:
    return {
        "id": tunnel.id,
        "profile": _serialize_profile(tunnel.profile),
        "status": _status_value(tunnel),
        "elapsed": _elapsed(tunnel),
        "last_error": tunnel.last_error,
    }


class BackendService:
    def __init__(self) -> None:
        self.store = ProfileStore()
        self.manager = TunnelManager()
        self.requests: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stop_requested = threading.Event()
        self.output_lock = threading.Lock()
        self.load_error = ""
        try:
            self.store.load()
        except ValueError as exc:
            self.load_error = str(exc)

    def emit(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with self.output_lock:
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()

    def respond(self, request_id: str, result: Any = None, error: str = "") -> None:
        payload: dict[str, Any] = {"id": request_id, "ok": not error}
        if error:
            payload["error"] = error
        else:
            payload["result"] = result
        self.emit(payload)

    def emit_manager_events(self) -> None:
        while True:
            try:
                event, tunnel_id, message = self.manager.events.get_nowait()
            except queue.Empty:
                return
            tunnel = self.manager.get(tunnel_id)
            self.emit(
                {
                    "event": "tunnel_event",
                    "data": {
                        "type": event,
                        "tunnel_id": tunnel_id,
                        "message": message,
                        "tunnel": _serialize_tunnel(tunnel) if tunnel else None,
                    },
                }
            )

    def handle(self, request: dict[str, Any]) -> None:
        request_id = str(request.get("id", ""))
        method = request.get("method")
        params = request.get("params") or {}
        try:
            result = self.dispatch(str(method), params)
            self.respond(request_id, result=result)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.respond(request_id, error=str(exc))
        except Exception as exc:  # keep the protocol alive across one bad request
            self.respond(request_id, error=f"服务内部错误：{exc}")

    def dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "get_status":
            return {"ssh_available": bool(self.manager.ssh_executable)}
        if method == "list_ssh_hosts":
            config = os.environ.get("SSH_FORWARDER_SSH_CONFIG")
            return {"hosts": discover_ssh_hosts(Path(config) if config else None)}
        if method == "load_profiles":
            if self.load_error:
                return {"profiles": [], "warning": self.load_error}
            return {
                "profiles": [_serialize_profile(item) for item in self.store.favorites]
            }
        if method == "get_tunnels":
            for tunnel in self.manager.snapshot():
                self.manager.mark_connected_if_running(tunnel.id)
            return {"tunnels": [_serialize_tunnel(item) for item in self.manager.snapshot()]}
        if method == "clear_finished":
            removed = 0
            for tunnel in self.manager.snapshot():
                if tunnel.process.poll() is not None:
                    self.manager.remove_finished(tunnel.id)
                    removed += 1
            return {"removed": removed}
        if method == "delete_tunnel":
            tunnel_id = str(params["tunnel_id"])
            tunnel = self.manager.get(tunnel_id)
            if tunnel and tunnel.process.poll() is None:
                raise ValueError("运行中的转发不能删除，请先停止。")
            self.manager.remove_finished(tunnel_id)
            return {"deleted": self.manager.get(tunnel_id) is None}
        if method == "save_profile":
            profile = ForwardProfile.from_dict(params["profile"])
            self.store.upsert(profile)
            return {"profile": _serialize_profile(profile)}
        if method == "delete_profile":
            self.store.delete(str(params["profile_id"]))
            return {"deleted": True}
        if method == "find_available_port":
            bind_address = str(params.get("bind_address", "127.0.0.1"))
            return {"port": find_available_port(bind_address)}
        if method == "start_tunnel":
            profile = ForwardProfile.from_dict(params["profile"])
            active = self.manager.start(profile)
            self.manager.mark_connected_if_running(active.id)
            return {"tunnel": _serialize_tunnel(active)}
        if method == "stop_tunnel":
            self.manager.stop(str(params["tunnel_id"]))
            return {"stopped": True}
        if method == "change_tunnel_port":
            active = self.manager.change_port(str(params["tunnel_id"]), params["local_port"])
            return {"tunnel": _serialize_tunnel(active)}
        if method == "shutdown":
            errors = self.manager.shutdown()
            self.stop_requested.set()
            if errors:
                raise RuntimeError("；".join(f"{item}: {message}" for item, message in errors))
            return {"stopped": True}
        raise ValueError(f"未知服务方法：{method}")

    def request_reader(self) -> None:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                if isinstance(request, dict):
                    self.requests.put(request)
            except json.JSONDecodeError as exc:
                self.emit({"event": "protocol_error", "message": str(exc)})
        self.requests.put({"_eof": True})

    def run(self) -> None:
        threading.Thread(target=self.request_reader, daemon=True).start()
        while not self.stop_requested.is_set():
            try:
                request = self.requests.get(timeout=0.1)
            except queue.Empty:
                self.emit_manager_events()
                continue
            if request.get("_eof"):
                self.manager.shutdown()
                break
            self.handle(request)
            self.emit_manager_events()


if __name__ == "__main__":
    BackendService().run()
