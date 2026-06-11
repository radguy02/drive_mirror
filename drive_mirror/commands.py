from __future__ import annotations

import argparse
import re
from pathlib import Path

from .auth import (
    build_drive_service,
    load_credentials,
    get_active_account,
    set_active_account,
    ACCOUNTS_DIR,
    get_token_path,
)
from .constants import (
    APP_NAME,
    CACHE_NAME,
    CONFIG_NAME,
    DRIVE_DIR,
    DRIVE_FOLDER_MIME,
    GOOGLE_APPS_PREFIX,
    MANIFEST_NAME,
    TOKEN_NAME,
)
from .errors import DriveMirrorError
from .ignore import is_ignored, load_ignore_rules
from .local import diff_local_manifest, scan_local
from .metadata import (
    empty_cache,
    empty_manifest,
    ensure_repository,
    load_manifest,
    metadata_path,
    read_json,
    save_cache,
    save_manifest,
    utc_now,
    write_json,
)
from .output import format_size, print_path_group
from .remote import (
    create_drive_folder,
    download_file,
    get_drive_file,
    scan_remote,
    trash_remote_file,
    upload_file,
)


def make_manifest_entry(
    local_file: dict[str, object],
    remote_file: dict[str, object],
) -> dict[str, object]:
    return {
        "path": local_file["path"],
        "sha256": local_file["sha256"],
        "size": local_file["size"],
        "mtime_ns": local_file["mtime_ns"],
        "remote_id": remote_file.get("id"),
        "remote_modified_time": remote_file.get("modified_time"),
        "remote_md5_checksum": remote_file.get("md5_checksum"),
        "last_sync": utc_now(),
    }


def cmd_login(args: argparse.Namespace) -> int:
    root = Path.cwd()
    service = build_drive_service(root, force_login=args.force)

    about = service.about().get(fields="user(emailAddress,displayName)").execute()
    user = about.get("user", {})
    display_name = user.get("displayName") or "Google account"
    email = user.get("emailAddress") or "unknown email"

    response = (
        service.files()
        .list(
            pageSize=args.limit,
            fields="files(id,name,mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )

    print(f"Authenticated as {display_name} <{email}>")
    print(f"Saved token: {get_token_path()}")
    print("Drive API access verified.")
    files = response.get("files", [])
    if files:
        print("Recent files:")
        for item in files:
            marker = "/" if item.get("mimeType") == DRIVE_FOLDER_MIME else ""
            print(f"  {item.get('name', '(unnamed)')}{marker}  {item.get('id')}")
    else:
        print("No Drive files were returned.")
    return 0


def cmd_auth_add(args: argparse.Namespace) -> int:
    root = Path.cwd()
    account_name = args.name
    # Force login for the specific account
    # We do this by calling load_credentials with force_login=True and the given account
    creds = load_credentials(root, force_login=True, account=account_name)
    if not creds:
        print("Failed to authenticate.")
        return 1
    
    print(f"Successfully authenticated and saved token for account: {account_name}")
    # Switch to this new account automatically
    set_active_account(account_name)
    print(f"Switched active account to: {account_name}")
    return 0


def cmd_auth_list(args: argparse.Namespace) -> int:
    # Ensure migration has run by calling get_token_path
    get_token_path()
    active = get_active_account()
    
    accounts = []
    if ACCOUNTS_DIR.exists():
        for path in ACCOUNTS_DIR.iterdir():
            if path.suffix == ".json":
                accounts.append(path.stem)
                
    if not accounts:
        print("No accounts configured.")
        return 0
        
    for acc in sorted(accounts):
        marker = "*" if acc == active else " "
        print(f"{marker} {acc}")
    return 0


def cmd_auth_use(args: argparse.Namespace) -> int:
    account_name = args.name
    target_path = ACCOUNTS_DIR / f"{account_name}.json"
    if not target_path.exists():
        raise DriveMirrorError(f"Account '{account_name}' does not exist. Add it with `drive auth add {account_name}` first.")
    
    set_active_account(account_name)
    print(f"Switched active account to: {account_name}")
    return 0


def cmd_auth_current(args: argparse.Namespace) -> int:
    active = get_active_account()
    print(f"Current account: {active}")
    return 0


def cmd_auth_remove(args: argparse.Namespace) -> int:
    account_name = args.name
    target_path = ACCOUNTS_DIR / f"{account_name}.json"
    active = get_active_account()
    
    if not target_path.exists():
        print(f"Account '{account_name}' does not exist.")
        return 1
        
    if account_name == active:
        # Check if there are other accounts
        accounts = [p.stem for p in ACCOUNTS_DIR.iterdir() if p.suffix == ".json"]
        if len(accounts) > 1:
            raise DriveMirrorError(f"Cannot remove the active account. Switch to another account first using `drive auth use <name>`.")
        else:
            # It's the only account, so deleting it is okay
            target_path.unlink()
            print(f"Removed account: {account_name}")
    else:
        target_path.unlink()
        print(f"Removed account: {account_name}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    drive_dir = root / DRIVE_DIR
    config_path = metadata_path(root, CONFIG_NAME)

    if config_path.exists() and not args.force:
        config = ensure_repository(root)
        print(f"Repository already initialized: {config.get('folder_id')}")
        return 0

    service = build_drive_service(root)

    if args.folder_id:
        folder = get_drive_file(service, args.folder_id)
        if folder.get("mimeType") != DRIVE_FOLDER_MIME:
            raise DriveMirrorError(f"{args.folder_id} is not a Google Drive folder.")
    else:
        folder = create_drive_folder(service, args.name or root.name)

    drive_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "version": 1,
        "app": APP_NAME,
        "root": str(root),
        "folder_id": folder["id"],
        "folder_name": folder.get("name", args.name or root.name),
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    write_json(config_path, config)

    if not metadata_path(root, MANIFEST_NAME).exists():
        write_json(metadata_path(root, MANIFEST_NAME), empty_manifest())
    if not metadata_path(root, CACHE_NAME).exists():
        write_json(metadata_path(root, CACHE_NAME), empty_cache())

    print(f"Initialized Drive repository in {root}")
    print(f"Linked Drive folder: {config['folder_name']} ({config['folder_id']})")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = Path.cwd()
    ensure_repository(root)
    local_files = scan_local(root)
    manifest = load_manifest(root)
    diff = diff_local_manifest(local_files, manifest.get("files", {}))

    if args.porcelain:
        for path in diff["added"]:
            print(f"A {path}")
        for path in diff["modified"]:
            print(f"M {path}")
        for path in diff["deleted"]:
            print(f"D {path}")
        return 0

    if not diff["added"] and not diff["modified"] and not diff["deleted"]:
        print("Repository is clean.")
        print(f"Tracked files: {len(manifest.get('files', {}))}")
        return 0

    print_path_group("Added", diff["added"])
    print_path_group("Modified", diff["modified"])
    print_path_group("Deleted", diff["deleted"])
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = ensure_repository(root)
    service = build_drive_service(root)
    manifest = load_manifest(root)
    manifest_files = manifest.get("files", {})
    local_files = scan_local(root)
    remote_index = scan_remote(service, config["folder_id"])
    diff = diff_local_manifest(local_files, manifest_files)

    upload_paths = sorted(
        set(diff["added"])
        | set(diff["modified"])
        | {path for path in local_files if path not in remote_index.files}
    )
    delete_paths = diff["deleted"]

    if args.dry_run:
        print_path_group("Would upload", upload_paths)
        if args.no_delete:
            print_path_group("Would leave deleted remote files untouched", delete_paths)
        else:
            print_path_group("Would move remote files to trash", delete_paths)
        print(f"Would skip unchanged files: {len(diff['unchanged'])}")
        return 0

    uploaded = 0
    for rel_path in upload_paths:
        upload_file(service, root, rel_path, remote_index)
        uploaded += 1
        print(f"Uploaded: {rel_path}")

    deleted = 0
    if not args.no_delete:
        for rel_path in delete_paths:
            remote_id = manifest_files.get(rel_path, {}).get("remote_id")
            if not remote_id and rel_path in remote_index.files:
                remote_id = remote_index.files[rel_path]["id"]
            if remote_id:
                trash_remote_file(service, remote_id)
                deleted += 1
                print(f"Moved to Drive trash: {rel_path}")

    remote_index = scan_remote(service, config["folder_id"])
    save_cache(root, remote_index)

    new_manifest_files = {
        rel_path: make_manifest_entry(local_file, remote_index.files[rel_path])
        for rel_path, local_file in local_files.items()
        if rel_path in remote_index.files
    }
    save_manifest(root, new_manifest_files)

    print(
        f"Push complete. Uploaded {uploaded}, "
        f"trashed {deleted}, skipped {len(diff['unchanged'])} unchanged."
    )
    if remote_index.duplicates:
        print("Warning: duplicate remote paths were detected and ignored:")
        for path in remote_index.duplicates:
            print(f"  {path}")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = ensure_repository(root)
    service = build_drive_service(root)
    manifest = load_manifest(root)
    manifest_files = manifest.get("files", {})
    local_before = scan_local(root)
    remote_index = scan_remote(service, config["folder_id"])
    rules = load_ignore_rules(root)

    downloaded_paths: set[str] = set()
    clean_paths: set[str] = set()
    conflict_paths: set[str] = set()
    skipped_workspace: list[str] = []
    skipped_ignored: list[str] = []

    for rel_path, remote_file in remote_index.files.items():
        if is_ignored(rel_path, False, rules):
            skipped_ignored.append(rel_path)
            continue

        if remote_file.get("mime_type", "").startswith(GOOGLE_APPS_PREFIX):
            skipped_workspace.append(rel_path)
            continue

        old_entry = manifest_files.get(rel_path)
        local_entry = local_before.get(rel_path)
        remote_changed = (
            not old_entry
            or old_entry.get("remote_id") != remote_file.get("id")
            or old_entry.get("remote_modified_time") != remote_file.get("modified_time")
        )
        local_changed = bool(
            old_entry and local_entry and local_entry["sha256"] != old_entry.get("sha256")
        )

        should_download = False
        if not local_entry:
            should_download = True
        elif not old_entry:
            if args.overwrite:
                should_download = True
            else:
                conflict_paths.add(rel_path)
        elif remote_changed:
            if local_changed and not args.overwrite:
                conflict_paths.add(rel_path)
            else:
                should_download = True
        elif local_changed:
            continue
        else:
            clean_paths.add(rel_path)

        if should_download:
            downloaded_paths.add(rel_path)
            if args.dry_run:
                print(f"Would download: {rel_path}")
            else:
                download_file(service, remote_file, root / rel_path)
                print(f"Downloaded: {rel_path}")

    if args.dry_run:
        print_path_group("Conflicts", sorted(conflict_paths))
        print_path_group("Ignored remote files", skipped_ignored)
        print_path_group("Skipped Google Workspace files", skipped_workspace)
        return 0

    save_cache(root, remote_index)
    local_after = scan_local(root)
    new_manifest_files = dict(manifest_files)
    for rel_path in downloaded_paths | clean_paths:
        if rel_path in local_after and rel_path in remote_index.files:
            new_manifest_files[rel_path] = make_manifest_entry(
                local_after[rel_path], remote_index.files[rel_path]
            )

    for rel_path in list(new_manifest_files):
        if rel_path not in local_after and rel_path not in remote_index.files:
            del new_manifest_files[rel_path]

    save_manifest(root, new_manifest_files)

    print(
        f"Pull complete. Downloaded {len(downloaded_paths)}, "
        f"skipped {len(clean_paths)} unchanged."
    )
    if conflict_paths:
        print("Conflicts skipped. Re-run with `drive pull --overwrite` to replace local files:")
        for path in sorted(conflict_paths):
            print(f"  {path}")
    if skipped_workspace:
        print("Skipped Google Workspace files because they need export handling:")
        for path in skipped_workspace:
            print(f"  {path}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = ensure_repository(root)
    manifest = load_manifest(root)
    cache = read_json(metadata_path(root, CACHE_NAME), default=empty_cache())
    local_count = len(scan_local(root)) if args.scan else None

    print(f"Repository root: {root}")
    print(f"Drive folder: {config.get('folder_name', '(unknown)')} ({config.get('folder_id')})")
    print(f"Metadata: {root / DRIVE_DIR}")
    print(f"Manifest files: {len(manifest.get('files', {}))}")
    if local_count is not None:
        print(f"Local files: {local_count}")
    print(f"Cached remote files: {len(cache.get('remote_files', {}))}")
    print(f"Last manifest update: {manifest.get('updated_at', 'never')}")
    print(f"Ignore file: {root / '.driveignore'}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = ensure_repository(root)
    service = build_drive_service(root)
    remote_index = scan_remote(service, config["folder_id"])
    save_cache(root, remote_index)

    if args.folders:
        for path, folder in remote_index.folders.items():
            if not path:
                continue
            print(f"{path}/  {folder['id']}" if args.long else f"{path}/")

    for path, item in remote_index.files.items():
        if args.long:
            print(
                f"{path}  {format_size(item.get('size'))}  "
                f"{item.get('modified_time') or '-'}  {item.get('id')}"
            )
        else:
            print(path)

    if not remote_index.files and not args.folders:
        print("No remote files found.")
    if remote_index.duplicates:
        print("Warning: duplicate remote paths were detected and ignored:")
        for path in remote_index.duplicates:
            print(f"  {path}")
    return 0


def safe_target_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return cleaned or "drive-repository"


def unique_target(base: Path) -> Path:
    if not base.exists():
        return base
    for number in range(1, 1000):
        candidate = base.with_name(f"{base.name}-{number}")
        if not candidate.exists():
            return candidate
    raise DriveMirrorError(f"Could not find an available clone target near {base}")


def cmd_clone(args: argparse.Namespace) -> int:
    root = Path.cwd()
    service = build_drive_service(root)
    folder = get_drive_file(service, args.folder_id)
    if folder.get("mimeType") != DRIVE_FOLDER_MIME:
        raise DriveMirrorError(f"{args.folder_id} is not a Google Drive folder.")

    if args.path:
        target = Path(args.path).expanduser()
        if not target.is_absolute():
            target = root / target
    else:
        target = unique_target(root / safe_target_name(folder.get("name", "drive-repository")))

    if target.exists() and any(target.iterdir()) and not args.force:
        raise DriveMirrorError(f"Clone target is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    (target / DRIVE_DIR).mkdir(parents=True, exist_ok=True)

    remote_index = scan_remote(service, args.folder_id)
    downloaded = 0
    skipped_workspace: list[str] = []
    skipped_metadata: list[str] = []

    for rel_path, remote_file in remote_index.files.items():
        if rel_path == DRIVE_DIR or rel_path.startswith(DRIVE_DIR + "/"):
            skipped_metadata.append(rel_path)
            continue
        if remote_file.get("mime_type", "").startswith(GOOGLE_APPS_PREFIX):
            skipped_workspace.append(rel_path)
            continue
        download_file(service, remote_file, target / rel_path)
        downloaded += 1
        print(f"Downloaded: {rel_path}")

    config = {
        "version": 1,
        "app": APP_NAME,
        "root": str(target),
        "folder_id": args.folder_id,
        "folder_name": folder.get("name"),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "cloned_from": args.folder_id,
    }
    write_json(metadata_path(target, CONFIG_NAME), config)
    save_cache(target, remote_index)

    local_files = scan_local(target)
    manifest_files = {
        rel_path: make_manifest_entry(local_file, remote_index.files[rel_path])
        for rel_path, local_file in local_files.items()
        if rel_path in remote_index.files
    }
    save_manifest(target, manifest_files)

    print(f"Clone complete: {target}")
    print(f"Downloaded {downloaded} files.")
    if skipped_metadata:
        print("Skipped remote .drive metadata to preserve the new local repository metadata.")
    if skipped_workspace:
        print("Skipped Google Workspace files because they need export handling:")
        for path in skipped_workspace:
            print(f"  {path}")
    return 0
