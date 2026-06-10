from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from .auth import import_google_api
from .constants import DRIVE_FOLDER_MIME
from .models import RemoteIndex


def quote_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def list_children(service: Any, folder_id: str) -> list[dict[str, Any]]:
    q = f"'{quote_query_value(folder_id)}' in parents and trashed = false"
    items: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=q,
                spaces="drive",
                fields=(
                    "nextPageToken, files("
                    "id,name,mimeType,modifiedTime,size,md5Checksum,parents)"
                ),
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return items


def get_drive_file(service: Any, file_id: str) -> dict[str, Any]:
    return (
        service.files()
        .get(
            fileId=file_id,
            fields="id,name,mimeType,modifiedTime,size,md5Checksum,driveId",
            supportsAllDrives=True,
        )
        .execute()
    )


def create_drive_folder(service: Any, name: str, parent_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"name": name, "mimeType": DRIVE_FOLDER_MIME}
    if parent_id:
        body["parents"] = [parent_id]
    return (
        service.files()
        .create(body=body, fields="id,name,mimeType,modifiedTime", supportsAllDrives=True)
        .execute()
    )


def find_child(
    service: Any,
    parent_id: str,
    name: str,
    mime_type: str | None = None,
) -> dict[str, Any] | None:
    q = (
        f"'{quote_query_value(parent_id)}' in parents "
        f"and name = '{quote_query_value(name)}' and trashed = false"
    )
    if mime_type:
        q += f" and mimeType = '{quote_query_value(mime_type)}'"
    response = (
        service.files()
        .list(
            q=q,
            spaces="drive",
            fields="files(id,name,mimeType,modifiedTime,size,md5Checksum,parents)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = response.get("files", [])
    return files[0] if files else None


def remote_file_entry(item: dict[str, Any], path: str, parent_id: str) -> dict[str, Any]:
    size = item.get("size")
    return {
        "id": item["id"],
        "name": item.get("name", ""),
        "path": path,
        "parent_id": parent_id,
        "mime_type": item.get("mimeType", ""),
        "modified_time": item.get("modifiedTime"),
        "size": int(size) if size is not None else None,
        "md5_checksum": item.get("md5Checksum"),
    }


def safe_remote_name(name: str) -> str:
    return name.replace("/", "_").replace("\0", "")


def join_remote_path(base_path: str, name: str) -> str:
    safe_name = safe_remote_name(name)
    return f"{base_path}/{safe_name}" if base_path else safe_name


def scan_remote(service: Any, folder_id: str) -> RemoteIndex:
    files: dict[str, dict[str, Any]] = {}
    folders: dict[str, dict[str, Any]] = {
        "": {"id": folder_id, "name": "", "path": "", "mime_type": DRIVE_FOLDER_MIME}
    }
    duplicates: list[str] = []
    visited_folders: set[str] = set()

    def walk(parent_id: str, base_path: str) -> None:
        if parent_id in visited_folders:
            return
        visited_folders.add(parent_id)

        for item in sorted(list_children(service, parent_id), key=lambda child: child.get("name", "")):
            child_path = join_remote_path(base_path, item.get("name", ""))
            if item.get("mimeType") == DRIVE_FOLDER_MIME:
                if child_path in folders:
                    duplicates.append(child_path + "/")
                    continue
                folders[child_path] = {
                    "id": item["id"],
                    "name": item.get("name", ""),
                    "path": child_path,
                    "parent_id": parent_id,
                    "mime_type": DRIVE_FOLDER_MIME,
                    "modified_time": item.get("modifiedTime"),
                }
                walk(item["id"], child_path)
            else:
                entry = remote_file_entry(item, child_path, parent_id)
                if child_path in files:
                    duplicates.append(child_path)
                    continue
                files[child_path] = entry

    walk(folder_id, "")
    return RemoteIndex(
        files=dict(sorted(files.items())),
        folders=dict(sorted(folders.items())),
        duplicates=duplicates,
    )


def ensure_remote_folder(
    service: Any,
    remote_index: RemoteIndex,
    folder_path: str,
) -> str:
    folder_path = folder_path.strip("/")
    if not folder_path:
        return remote_index.folders[""]["id"]
    if folder_path in remote_index.folders:
        return remote_index.folders[folder_path]["id"]

    parent_path = ""
    parent_id = remote_index.folders[""]["id"]
    for part in folder_path.split("/"):
        next_path = f"{parent_path}/{part}" if parent_path else part
        if next_path in remote_index.folders:
            parent_id = remote_index.folders[next_path]["id"]
            parent_path = next_path
            continue

        existing = find_child(service, parent_id, part, DRIVE_FOLDER_MIME)
        if existing:
            folder = existing
        else:
            folder = create_drive_folder(service, part, parent_id)

        remote_index.folders[next_path] = {
            "id": folder["id"],
            "name": folder.get("name", part),
            "path": next_path,
            "parent_id": parent_id,
            "mime_type": DRIVE_FOLDER_MIME,
            "modified_time": folder.get("modifiedTime"),
        }
        parent_id = folder["id"]
        parent_path = next_path

    return parent_id


def upload_file(
    service: Any,
    root: Path,
    rel_path: str,
    remote_index: RemoteIndex,
) -> dict[str, Any]:
    google = import_google_api()
    local_path = root / rel_path
    folder_path, filename = os.path.split(rel_path)
    parent_id = ensure_remote_folder(service, remote_index, folder_path)
    media = google["MediaFileUpload"](str(local_path), resumable=True)

    existing = remote_index.files.get(rel_path) or find_child(service, parent_id, filename)
    if existing:
        metadata = (
            service.files()
            .update(
                fileId=existing["id"],
                body={"name": filename},
                media_body=media,
                fields="id,name,mimeType,modifiedTime,size,md5Checksum,parents",
                supportsAllDrives=True,
            )
            .execute()
        )
    else:
        metadata = (
            service.files()
            .create(
                body={"name": filename, "parents": [parent_id]},
                media_body=media,
                fields="id,name,mimeType,modifiedTime,size,md5Checksum,parents",
                supportsAllDrives=True,
            )
            .execute()
        )

    entry = remote_file_entry(metadata, rel_path, parent_id)
    remote_index.files[rel_path] = entry
    return entry


def trash_remote_file(service: Any, file_id: str) -> None:
    (
        service.files()
        .update(fileId=file_id, body={"trashed": True}, fields="id,trashed", supportsAllDrives=True)
        .execute()
    )


def download_file(service: Any, remote_file: dict[str, Any], destination: Path) -> None:
    google = import_google_api()
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(destination.name + ".drivepart")
    request = service.files().get_media(fileId=remote_file["id"], supportsAllDrives=True)
    with io.FileIO(tmp_path, "wb") as fh:
        downloader = google["MediaIoBaseDownload"](fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    tmp_path.replace(destination)
