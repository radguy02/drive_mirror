from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import CACHE_NAME, CONFIG_NAME, DRIVE_DIR, MANIFEST_NAME
from .errors import DriveMirrorError
from .models import RemoteIndex


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def metadata_path(root: Path, name: str) -> Path:
    return root / DRIVE_DIR / name


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise DriveMirrorError(f"Could not parse JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp_path.replace(path)


def ensure_repository(root: Path) -> dict[str, Any]:
    config = read_json(metadata_path(root, CONFIG_NAME), default=None)
    if not config or not config.get("folder_id"):
        raise DriveMirrorError(
            f"{root} is not initialized. Run `drive init` from this folder first."
        )
    return config


def empty_manifest() -> dict[str, Any]:
    return {"version": 1, "updated_at": utc_now(), "files": {}}


def empty_cache() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": utc_now(),
        "remote_files": {},
        "remote_folders": {},
        "duplicates": [],
    }


def load_manifest(root: Path) -> dict[str, Any]:
    manifest = read_json(metadata_path(root, MANIFEST_NAME), default=None)
    if not manifest:
        return empty_manifest()
    manifest.setdefault("files", {})
    return manifest


def save_manifest(root: Path, files: dict[str, dict[str, Any]]) -> None:
    write_json(
        metadata_path(root, MANIFEST_NAME),
        {"version": 1, "updated_at": utc_now(), "files": files},
    )


def save_cache(root: Path, remote_index: RemoteIndex) -> None:
    write_json(
        metadata_path(root, CACHE_NAME),
        {
            "version": 1,
            "updated_at": utc_now(),
            "remote_files": remote_index.files,
            "remote_folders": remote_index.folders,
            "duplicates": remote_index.duplicates,
        },
    )
