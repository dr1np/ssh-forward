from __future__ import annotations

import glob
import os
import shlex
from pathlib import Path


WILDCARD_MARKERS = frozenset("*?![")


def _split_config_line(line: str) -> tuple[str, list[str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return "", []
    try:
        parts = shlex.split(stripped, comments=True, posix=True)
    except ValueError:
        return "", []
    if not parts:
        return "", []
    if "=" in parts[0]:
        key, first_value = parts[0].split("=", 1)
        values = ([first_value] if first_value else []) + parts[1:]
        return key.lower(), values
    if len(parts) > 1 and parts[1] == "=":
        return parts[0].lower(), parts[2:]
    return parts[0].lower(), parts[1:]


def _expand_include(pattern: str, parent: Path) -> list[Path]:
    expanded = os.path.expandvars(os.path.expanduser(pattern))
    path = Path(expanded)
    if not path.is_absolute():
        path = parent / path
    return [Path(item) for item in sorted(glob.glob(str(path)))]


def discover_ssh_hosts(config_file: Path | None = None) -> list[str]:
    """Return concrete Host aliases, following OpenSSH Include directives."""

    root = config_file or Path.home() / ".ssh" / "config"
    hosts: list[str] = []
    seen_hosts: set[str] = set()
    visited: set[Path] = set()

    def parse(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in visited or not resolved.is_file():
            return
        visited.add(resolved)
        try:
            lines = resolved.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            return
        for line in lines:
            key, values = _split_config_line(line)
            if key == "include":
                for pattern in values:
                    for included in _expand_include(pattern, resolved.parent):
                        parse(included)
            elif key == "host":
                for host in values:
                    if host.startswith("!") or any(mark in host for mark in WILDCARD_MARKERS):
                        continue
                    normalized = host.casefold()
                    if normalized not in seen_hosts:
                        seen_hosts.add(normalized)
                        hosts.append(host)

    parse(root)
    return hosts
