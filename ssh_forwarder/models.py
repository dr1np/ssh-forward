from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
        if not self.name.strip():
            raise ValueError("请填写配置名称。")
        if not self.ssh_host.strip():
            raise ValueError("请填写 SSH 主机。")
        if not self.remote_host.strip():
            raise ValueError("请填写目标主机。")
        if self.connection_type not in {"config", "custom"}:
            raise ValueError("连接类型无效。")
        if not 1 <= int(self.local_port) <= 65535:
            raise ValueError("本地端口必须在 1 到 65535 之间。")
        if not 1 <= int(self.remote_port) <= 65535:
            raise ValueError("目标端口必须在 1 到 65535 之间。")
        if not 1 <= int(self.ssh_port) <= 65535:
            raise ValueError("SSH 端口必须在 1 到 65535 之间。")
        if self.local_bind not in {"127.0.0.1", "0.0.0.0", "::1"}:
            raise ValueError("本地监听地址无效。")

    def clone(self, *, keep_id: bool = True) -> "ForwardProfile":
        values = asdict(self)
        if not keep_id:
            values["id"] = uuid4().hex
        return ForwardProfile(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForwardProfile":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)

    @property
    def ssh_destination(self) -> str:
        if self.connection_type == "custom" and self.ssh_user.strip():
            return f"{self.ssh_user.strip()}@{self.ssh_host.strip()}"
        return self.ssh_host.strip()

    @property
    def local_endpoint(self) -> str:
        host = "localhost" if self.local_bind in {"127.0.0.1", "::1"} else self.local_bind
        return f"{host}:{self.local_port}"

    @property
    def target_endpoint(self) -> str:
        return f"{self.remote_host}:{self.remote_port}"


@dataclass(slots=True)
class ActiveTunnel:
    id: str
    profile: ForwardProfile
    process: Any
    status: str = "正在连接"
    started_at: datetime = field(default_factory=datetime.now)
    last_error: str = ""

