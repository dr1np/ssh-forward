from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import ForwardProfile


APP_NAME = "SSHForwarder"


def default_data_file() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / APP_NAME / "settings.json"


class ProfileStore:
    """Small JSON store with atomic writes for favorites and UI preferences."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_data_file()
        self.favorites: list[ForwardProfile] = []
        self.preferences: dict[str, Any] = {}
        self.load_failed = False

    def load(self) -> None:
        self.favorites = []
        self.preferences = {}
        self.load_failed = False
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("配置文件根节点不是对象")
            favorites = payload.get("favorites", [])
            if not isinstance(favorites, list):
                raise ValueError("收藏列表不是数组")
            seen_ids: set[str] = set()
            for item in favorites:
                if not isinstance(item, dict):
                    continue
                try:
                    profile = ForwardProfile.from_dict(item)
                    profile.validate()
                    if profile.id in seen_ids:
                        continue
                    seen_ids.add(profile.id)
                    self.favorites.append(profile)
                except (TypeError, ValueError):
                    continue
            preferences = payload.get("preferences", {})
            if isinstance(preferences, dict):
                self.preferences = preferences
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.load_failed = True
            raise ValueError(f"无法读取配置文件：{exc}") from exc

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "favorites": [profile.to_dict() for profile in self.favorites],
            "preferences": self.preferences,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, self.path)
        self.load_failed = False

    def upsert(self, profile: ForwardProfile) -> None:
        profile.validate()
        saved = profile.clone(keep_id=True)
        for index, item in enumerate(self.favorites):
            if item.id == saved.id:
                self.favorites[index] = saved
                self.save()
                return
        self.favorites.append(saved)
        self.save()

    def delete(self, profile_id: str) -> None:
        self.favorites = [item for item in self.favorites if item.id != profile_id]
        self.save()

    def get(self, profile_id: str) -> ForwardProfile | None:
        return next((item for item in self.favorites if item.id == profile_id), None)
