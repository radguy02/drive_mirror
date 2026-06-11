from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import CREDENTIALS_NAME, SCOPES, TOKEN_NAME
from .errors import DriveMirrorError
from .metadata import read_json

CONFIG_DIR = Path.home() / ".config" / "drive-mirror"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNTS_DIR = CONFIG_DIR / "accounts"
GLOBAL_CONFIG_PATH = CONFIG_DIR / "config.json"
CREDENTIALS_PATH = CONFIG_DIR / CREDENTIALS_NAME


def get_active_account() -> str:
    if not GLOBAL_CONFIG_PATH.exists():
        return "default"
    try:
        import json
        with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("active_account", "default")
    except Exception:
        return "default"


def set_active_account(name: str) -> None:
    import json
    data = {}
    if GLOBAL_CONFIG_PATH.exists():
        try:
            with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["active_account"] = name
    with open(GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def migrate_old_token() -> None:
    old_token_path = CONFIG_DIR / TOKEN_NAME
    if old_token_path.exists() and not ACCOUNTS_DIR.exists():
        ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
        default_token_path = ACCOUNTS_DIR / "default.json"
        old_token_path.rename(default_token_path)
        set_active_account("default")
    else:
        ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)


def get_token_path(account: str | None = None) -> Path:
    migrate_old_token()
    if account is None:
        account = get_active_account()
    return ACCOUNTS_DIR / f"{account}.json"


def import_google_api() -> dict[str, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    except ImportError as exc:
        raise DriveMirrorError(
            "Missing Google API packages. Install them with:\n"
            "  python -m pip install -r requirements.txt"
        ) from exc

    return {
        "Request": Request,
        "Credentials": Credentials,
        "InstalledAppFlow": InstalledAppFlow,
        "build": build,
        "HttpError": HttpError,
        "MediaFileUpload": MediaFileUpload,
        "MediaIoBaseDownload": MediaIoBaseDownload,
    }


def find_credentials_file(root: Path) -> Path:
    if CREDENTIALS_PATH.exists():
        return CREDENTIALS_PATH

    project_root = Path(__file__).resolve().parent.parent

    candidates = [root / CREDENTIALS_NAME]

    if project_root != root:
        candidates.append(project_root / CREDENTIALS_NAME)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    checked = ", ".join(
        [str(CREDENTIALS_PATH)] + [str(path) for path in candidates]
    )

    raise DriveMirrorError(
        f"Could not find {CREDENTIALS_NAME}. Checked: {checked}\n"
        "Create an OAuth desktop client in Google Cloud Console and place the JSON file there."
    )


def credentials_have_scopes(creds: Any) -> bool:
    has_scopes = getattr(creds, "has_scopes", None)
    if callable(has_scopes):
        return bool(has_scopes(SCOPES))
    return True


def token_file_has_requested_scopes(token_path: Path) -> bool:
    token_data = read_json(token_path, default={})
    raw_scopes = token_data.get("scopes") or token_data.get("scope")
    if not raw_scopes:
        return True
    if isinstance(raw_scopes, str):
        token_scopes = set(raw_scopes.split())
    else:
        token_scopes = set(raw_scopes)
    return set(SCOPES).issubset(token_scopes)


def load_credentials(root: Path, force_login: bool = False, account: str | None = None) -> Any:
    google = import_google_api()
    token_path = get_token_path(account)

    creds = None

    if token_path.exists() and not force_login and token_file_has_requested_scopes(token_path):
        creds = google["Credentials"].from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token and credentials_have_scopes(creds):
        try:
            creds.refresh(google["Request"]())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            creds = None

    if (
        not creds
        or not getattr(creds, "valid", False)
        or not credentials_have_scopes(creds)
        or force_login
    ):
        credentials_path = find_credentials_file(root)
        flow = google["InstalledAppFlow"].from_client_secrets_file(str(credentials_path), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def build_drive_service(root: Path, force_login: bool = False) -> Any:
    google = import_google_api()
    creds = load_credentials(root, force_login=force_login)
    return google["build"]("drive", "v3", credentials=creds)
