import sys
import time

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


def truncate_filename(filename: str, max_width: int = 30) -> str:
    if len(filename) <= max_width:
        return filename
    
    if "." in filename:
        parts = filename.rsplit(".", 1)
        ext = "." + parts[1]
        name = parts[0]
    else:
        ext = ""
        name = filename
        
    keep_len = max_width - 3 - len(ext)
    if keep_len > 0:
        return name[:keep_len] + "..." + ext
    else:
        return filename[:max_width-3] + "..."


def format_speed(speed_bps: float) -> str:
    return f"{format_size(int(speed_bps))}/s"


def format_transfer_line(
    symbol: str, 
    filename: str, 
    current: int, 
    total: int | None, 
    speed_bps: float | None = None,
    state: str = "active"
) -> str:
    fname = truncate_filename(filename, 30).ljust(30)
    
    if state == "failed":
        return f"{symbol} {fname}  Transfer Failed"
        
    size_str = f"{format_size(current)} / {format_size(total)}".rjust(17)
    
    if state == "complete":
        return f"{symbol} {fname}  {size_str}    Complete"
        
    speed_str = format_speed(speed_bps or 0).rjust(11)
    return f"{symbol} {fname}  {size_str}  {speed_str}"


class TransferTracker:
    def __init__(self, filename: str, direction: str):
        self.filename = filename
        self.direction = direction
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_bytes = 0
        self.symbol = "⬆" if direction == "up" else "⬇"
        self._print(0, None, state="active")

    def update(self, current: int, total: int | None):
        now = time.time()
        dt = now - self.last_update_time
        if dt > 0.2 or (total is not None and current == total):
            speed = 0.0
            if dt > 0:
                speed = (current - self.last_bytes) / dt
            self.last_update_time = now
            self.last_bytes = current
            self._print(current, total, speed, state="active")

    def complete(self, total: int | None = None):
        self.symbol = "✔"
        if total is None:
            total = self.last_bytes
        self._print(total, total, state="complete")
        print()

    def fail(self):
        self.symbol = "✖"
        self._print(0, None, state="failed")
        print()

    def _print(self, current: int, total: int | None, speed: float | None = None, state: str = "active"):
        line = format_transfer_line(self.symbol, self.filename, current, total, speed, state)
        sys.stdout.write(f"\r{line}\033[K")
        sys.stdout.flush()
