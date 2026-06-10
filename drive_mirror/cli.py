from __future__ import annotations

import argparse
import sys

from .auth import import_google_api
from .commands import (
    cmd_clone,
    cmd_info,
    cmd_init,
    cmd_list,
    cmd_login,
    cmd_pull,
    cmd_push,
    cmd_status,
)
from .errors import DriveMirrorError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="drive", description="Mirror a folder to Google Drive.")
    subparsers = parser.add_subparsers(dest="command")

    login = subparsers.add_parser("login", help="Authenticate with Google Drive.")
    login.add_argument("--force", action="store_true", help="Run OAuth even if token.json exists.")
    login.add_argument("--limit", type=int, default=10, help="Number of files to list for verification.")
    login.set_defaults(func=cmd_login)

    init = subparsers.add_parser("init", help="Initialize the current folder as a Drive repository.")
    init.add_argument("--name", help="Name for the remote Drive folder.")
    init.add_argument("--folder-id", help="Link to an existing Drive folder instead of creating one.")
    init.add_argument("--force", action="store_true", help="Overwrite existing local repository config.")
    init.set_defaults(func=cmd_init)

    push = subparsers.add_parser("push", help="Upload local changes to Drive.")
    push.add_argument("--dry-run", action="store_true", help="Show what would be uploaded.")
    push.add_argument(
        "--no-delete",
        action="store_true",
        help="Do not move remotely tracked files to trash when they are deleted locally.",
    )
    push.set_defaults(func=cmd_push)

    pull = subparsers.add_parser("pull", help="Download remote changes from Drive.")
    pull.add_argument("--dry-run", action="store_true", help="Show what would be downloaded.")
    pull.add_argument("--overwrite", action="store_true", help="Overwrite local files on conflicts.")
    pull.set_defaults(func=cmd_pull)

    status = subparsers.add_parser("status", help="Show local changes since the last sync.")
    status.add_argument("--porcelain", action="store_true", help="Print machine-readable status.")
    status.set_defaults(func=cmd_status)

    info = subparsers.add_parser("info", help="Show repository information.")
    info.add_argument("--scan", action="store_true", help="Count current local files.")
    info.set_defaults(func=cmd_info)

    list_remote = subparsers.add_parser("list", help="List files in the linked Drive folder.")
    list_remote.add_argument("-l", "--long", action="store_true", help="Show ids and metadata.")
    list_remote.add_argument("--folders", action="store_true", help="Include folders.")
    list_remote.set_defaults(func=cmd_list)

    clone = subparsers.add_parser("clone", help="Clone an existing Drive repository.")
    clone.add_argument("folder_id", help="Google Drive folder id to clone.")
    clone.add_argument("path", nargs="?", help="Optional local target path.")
    clone.add_argument("--force", action="store_true", help="Allow cloning into a non-empty folder.")
    clone.set_defaults(func=cmd_clone)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    try:
        return int(args.func(args))
    except DriveMirrorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCanceled.", file=sys.stderr)
        return 130
    except Exception as exc:
        google_error = None
        try:
            google_error = import_google_api()["HttpError"]
        except DriveMirrorError:
            pass
        if google_error and isinstance(exc, google_error):
            print(f"Google Drive API error: {exc}", file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
