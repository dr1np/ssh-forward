from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ForwardProfile:
    """A reusable local SSH port-forward definition."""

    name: str
    ssh_host: str
    local_port: int
    remote_host: str
    remote_port: int
    connection_type: str = "config"
    ssh_port: int = 22
    ssh_user: str = ""
    identity_file: str = ""
    local_bind: str = "127.0.0.1"
    id: str = field(default_factory=lambda: uuid4().hex)

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("请填写配置名称。")
        if not isinstance(self.ssh_host, str) or not self.ssh_host.strip():
            raise ValueError("请填写 SSH 主机。")
        if not isinstance(self.remote_host, str) or not self.remote_host.strip():
            raise ValueError("请填写目标主机。")
        for host, label in ((self.ssh_host, "SSH 主机"), (self.remote_host, "目标主机")):
            if host.strip().startswith("-") or any(char.isspace() for char in host.strip()) or "\x00" in host:
                raise ValueError(f"{label}不能包含空白字符或以 - 开头。")
        if not isinstance(self.connection_type, str) or self.connection_type not in {"config", "custom"}:
            raise ValueError("连接类型无效。")
        for value, label in (
            (self.local_port, "本地端口"),
            (self.remote_port, "目标端口"),
            (self.ssh_port, "SSH 端口"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{label}必须是整数。")
            if not 1 <= value <= 65535:
                raise ValueError(f"{label}必须在 1 到 65535 之间。")
        if not isinstance(self.ssh_user, str) or not isinstance(self.identity_file, str):
            raise ValueError("SSH 用户名或私钥路径格式无效。")
        if not isinstance(self.local_bind, str) or self.local_bind not in {"127.0.0.1", "0.0.0.0", "::1"}:
            raise ValueError("本地监听地址无效。")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("配置 ID 无效。")

    def clone(self, *, keep_id: bool = True) -> "ForwardProfile":
        values = asdict(self)
        if not keep_id:
            values["id"] = uuid4().hex
        return ForwardProfile(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForwardProfile":
        if not isinstance(data, dict):
            raise ValueError("收藏格式无效。")
        allowed = {item.name for item in fields(cls)}
        values = {key: value for key, value in data.items() if key in allowed}
        try:
            return cls(**values)
        except TypeError as exc:
            raise ValueError("收藏字段缺失或格式无效。") from exc

    @property
    def ssh_destination(self) -> str:
        if self.connection_type == "custom" and self.ssh_user.strip():
            return f"{self.ssh_user.strip()}@{self.ssh_host.strip()}"
        return self.ssh_host.strip()

    @property
    def local_endpoint(self) -> str:
        host = "localhost" if self.local_bind == "127.0.0.1" else self.local_bind
        return _format_endpoint(host, self.local_port)

    @property
    def target_endpoint(self) -> str:
        return _format_endpoint(self.remote_host, self.remote_port)


def _format_endpoint(host: str, port: int) -> str:
    value = host.strip()
    if ":" in value and not (value.startswith("[") and value.endswith("]")):
        value = f"[{value}]"
    return f"{value}:{port}"


@dataclass(slots=True)
class ActiveTunnel:
    id: str
    profile: ForwardProfile
    process: Any
    status: str = "正在连接"
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None
    last_error: str = ""
