from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IgnoreRule:
    pattern: str
    dir_only: bool
    anchored: bool
    has_slash: bool


@dataclass
class RemoteIndex:
    files: dict[str, dict[str, Any]]
    folders: dict[str, dict[str, Any]]
    duplicates: list[str]
