from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from .ignore import is_ignored, load_ignore_rules


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_local(root: Path) -> dict[str, dict[str, Any]]:
    rules = load_ignore_rules(root)
    files: dict[str, dict[str, Any]] = {}

    for current_dir, dirnames, filenames in os.walk(root):
        current = Path(current_dir)

        kept_dirs = []
        for dirname in dirnames:
            rel_dir = (current / dirname).relative_to(root).as_posix()
            if not is_ignored(rel_dir, True, rules):
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            path = current / filename
            rel_path = path.relative_to(root).as_posix()
            if is_ignored(rel_path, False, rules) or not path.is_file():
                continue

            stat = path.stat()
            files[rel_path] = {
                "path": rel_path,
                "absolute_path": str(path),
                "sha256": sha256_file(path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }

    return dict(sorted(files.items()))


def diff_local_manifest(
    local_files: dict[str, dict[str, Any]],
    manifest_files: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    local_paths = set(local_files)
    manifest_paths = set(manifest_files)
    added = sorted(local_paths - manifest_paths)
    deleted = sorted(manifest_paths - local_paths)
    modified = sorted(
        path
        for path in local_paths & manifest_paths
        if local_files[path]["sha256"] != manifest_files[path].get("sha256")
    )
    unchanged = sorted(
        path
        for path in local_paths & manifest_paths
        if local_files[path]["sha256"] == manifest_files[path].get("sha256")
    )
    return {
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "unchanged": unchanged,
    }
