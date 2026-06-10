from __future__ import annotations

import fnmatch
from pathlib import Path

from .constants import DEFAULT_IGNORES
from .models import IgnoreRule


def parse_ignore_line(line: str) -> IgnoreRule | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    stripped = stripped.replace("\\", "/")
    anchored = stripped.startswith("/")
    if anchored:
        stripped = stripped[1:]

    dir_only = stripped.endswith("/")
    if dir_only:
        stripped = stripped.rstrip("/")

    stripped = stripped.strip("/")
    if not stripped:
        return None

    return IgnoreRule(
        pattern=stripped,
        dir_only=dir_only,
        anchored=anchored,
        has_slash="/" in stripped,
    )


def load_ignore_rules(root: Path) -> list[IgnoreRule]:
    rules: list[IgnoreRule] = []
    for raw in DEFAULT_IGNORES:
        rule = parse_ignore_line(raw)
        if rule:
            rules.append(rule)

    ignore_file = root / ".driveignore"
    if ignore_file.exists():
        for line in ignore_file.read_text(encoding="utf-8").splitlines():
            rule = parse_ignore_line(line)
            if rule:
                rules.append(rule)
    return rules


def path_matches_rule(rel_path: str, is_dir: bool, rule: IgnoreRule) -> bool:
    rel_path = rel_path.replace("\\", "/").strip("/")
    if not rel_path:
        return False

    parts = rel_path.split("/")
    basename = parts[-1]

    if rule.dir_only:
        if rule.anchored or rule.has_slash:
            return (
                rel_path == rule.pattern
                or rel_path.startswith(rule.pattern + "/")
                or (is_dir and fnmatch.fnmatch(rel_path, rule.pattern))
            )
        candidate_parts = parts if is_dir else parts[:-1]
        return any(fnmatch.fnmatch(part, rule.pattern) for part in candidate_parts)

    if rule.anchored or rule.has_slash:
        return fnmatch.fnmatch(rel_path, rule.pattern)

    return fnmatch.fnmatch(basename, rule.pattern) or fnmatch.fnmatch(rel_path, rule.pattern)


def is_ignored(rel_path: str, is_dir: bool, rules: list[IgnoreRule]) -> bool:
    return any(path_matches_rule(rel_path, is_dir, rule) for rule in rules)
