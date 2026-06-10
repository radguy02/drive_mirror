def print_path_group(label: str, paths: list[str]) -> None:
    if not paths:
        return
    print(f"{label}:")
    for path in paths:
        print(f"  {path}")


def format_size(size: int | None) -> str:
    if size is None:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
