APP_NAME = "Drive Mirror"
SCOPES = ["https://www.googleapis.com/auth/drive"]

DRIVE_DIR = ".drive"
CONFIG_NAME = "config.json"
MANIFEST_NAME = "manifest.json"
CACHE_NAME = "cache.json"
CREDENTIALS_NAME = "credentials.json"
TOKEN_NAME = "token.json"

DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_APPS_PREFIX = "application/vnd.google-apps."

DEFAULT_IGNORES = [
    ".drive/",
    ".git/",
    ".agents/",
    ".codex/",
    "venv/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.log",
    CREDENTIALS_NAME,
    TOKEN_NAME,
]
