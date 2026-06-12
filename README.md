# Drive Mirror

A lightweight, Git-inspired CLI tool that mirrors a local folder to a Google Drive folder. Push local changes, pull remote updates, manage multiple Google accounts, and keep everything in sync — all from the terminal.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Google Cloud Setup](#google-cloud-setup)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [Authentication](#authentication)
  - [Multi-Account Management](#multi-account-management)
  - [Repository Initialization](#repository-initialization)
  - [Synchronization](#synchronization)
  - [Information & Inspection](#information--inspection)
  - [Cloning](#cloning)
- [Ignore Rules](#ignore-rules)
- [Repository Metadata](#repository-metadata)
- [Project Architecture](#project-architecture)
- [Configuration Paths](#configuration-paths)
- [License](#license)

---

## Features

- **Push & Pull Sync** — Upload local changes to Drive or download remote updates with a single command.
- **SHA-256 Change Detection** — Files are tracked by content hash, not modification time, so only truly changed files are transferred.
- **Multi-Account Support** — Authenticate with multiple Google Drive accounts and switch between them seamlessly.
- **Clone Remote Folders** — Clone an existing Drive folder into a new local directory, like `git clone` but for Google Drive.
- **`.driveignore` File** — Gitignore-style pattern matching to exclude files and directories from sync.
- **Conflict Detection** — Pull warns about local/remote conflicts and never overwrites without explicit consent.
- **Dry Run Mode** — Preview what would be uploaded, downloaded, or deleted before making any changes.
- **Resumable Transfers** — Uploads and downloads use 1 MB chunked, resumable transfers with automatic retries.
- **Real-Time Progress** — Live transfer progress with speed indicators (`⬆` / `⬇`) and completion status (`✔` / `✖`).
- **Shared Drive Support** — Full compatibility with Google Shared Drives (Team Drives).
- **Atomic File Writes** — All metadata and downloads are written atomically via temporary files to prevent corruption.
- **Duplicate Detection** — Warns about duplicate file/folder names on Drive that could cause sync ambiguity.
- **Cross-Platform** — Uses Python's `pathlib` throughout; works on Linux, macOS, and Windows.

---

## Prerequisites

- **Python 3.10** or later
- A **Google Cloud project** with the Google Drive API enabled
- An **OAuth 2.0 Desktop Client** credential (`credentials.json`)

---

## Installation

### Option 1: Install from source with pip

```bash
git clone https://github.com/radguy02/drive_mirror.git
cd drive-mirror
pip install .
```

After installation, the `drive` command is available globally:

```bash
drive login
drive init
drive push
```

### Option 2: Run directly without installing

```bash
git clone https://github.com/radguy02/drive_mirror.git
cd drive-mirror
pip install -r requirements.txt
```

Then use the `./drive` script from the project root:

```bash
./drive login
./drive init
./drive push
```

> **Tip:** You can symlink `./drive` into a directory on your `PATH` (e.g. `~/.local/bin/`) to use it from anywhere.

---

## Google Cloud Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Navigate to **APIs & Services → Library** and enable the **Google Drive API**.
4. Go to **APIs & Services → Credentials** and create an **OAuth 2.0 Client ID** (application type: **Desktop app**).
5. Download the client configuration JSON and save it as `credentials.json`.
6. Place `credentials.json` in one of the following locations (checked in order):
   - `~/.config/drive-mirror/credentials.json` *(recommended — works globally)*
   - The current working directory
   - The Drive Mirror project root

---

## Quick Start

```bash
# 1. Authenticate with Google Drive
drive login

# 2. Navigate to the folder you want to mirror
cd ~/my-project

# 3. Initialize a Drive Mirror repository
drive init --name "My Project Backup"

# 4. Push all local files to Drive
drive push

# 5. Check sync status at any time
drive status
```

---

## Commands

### Authentication

#### `drive login`

Authenticate with Google Drive via OAuth. Opens a browser window for the Google sign-in flow, saves the token, and verifies API access by listing recent files.

```bash
drive login            # Authenticate (skipped if token already exists)
drive login --force    # Re-authenticate even if a valid token exists
drive login --limit 5  # Show 5 recent files for verification (default: 10)
```

---

### Multi-Account Management

Drive Mirror supports authenticating and switching between multiple Google Drive accounts. Tokens are stored under `~/.config/drive-mirror/accounts/`.

#### `drive auth add <name>`

Add a new Google account. Opens the OAuth flow, saves the token under the given name, and switches to it automatically.

```bash
drive auth add personal
drive auth add work
```

#### `drive auth list`

List all configured accounts. The active account is marked with `*`.

```bash
drive auth list
# Output:
#   personal
# * work
```

#### `drive auth use <name>`

Switch the active account.

```bash
drive auth use personal
```

#### `drive auth current`

Display the currently active account name.

```bash
drive auth current
# Output: Current account: personal
```

#### `drive auth remove <name>`

Remove a saved account and its token. You cannot remove the active account if other accounts exist — switch first.

```bash
drive auth remove work
```

---

### Repository Initialization

#### `drive init`

Initialize the current directory as a Drive Mirror repository. Creates a `.drive/` metadata directory and links the folder to a Google Drive folder.

```bash
drive init                         # Create a new Drive folder named after the current directory
drive init --name "Project Alpha"  # Create a new Drive folder with a custom name
drive init --folder-id <ID>        # Link to an existing Drive folder by its ID
drive init --force                 # Re-initialize, overwriting existing config
```

---

### Synchronization

#### `drive push`

Upload local changes to the linked Drive folder. Detects added, modified, and deleted files by comparing SHA-256 hashes against the local manifest.

```bash
drive push              # Upload all changes
drive push --dry-run    # Preview changes without uploading
drive push --no-delete  # Upload new/modified files but keep remotely deleted files
```

**Behavior:**
- **New files** are created on Drive, with parent folders auto-created as needed.
- **Modified files** are updated in-place (same remote file ID is reused).
- **Locally deleted files** are moved to the Drive trash (unless `--no-delete` is specified).
- Unchanged files are skipped entirely.

#### `drive pull`

Download remote changes from the linked Drive folder.

```bash
drive pull              # Download remote changes
drive pull --dry-run    # Preview what would be downloaded
drive pull --overwrite  # Force overwrite local files on conflicts
```

**Behavior:**
- **New remote files** (not present locally) are downloaded.
- **Remotely updated files** are re-downloaded if the local copy hasn't changed.
- **Conflicts** (both local and remote changed) are skipped with a warning. Use `--overwrite` to force the remote version.
- **Google Workspace files** (Docs, Sheets, Slides, etc.) are skipped with a notice, as they require export handling.
- Ignored files (via `.driveignore`) are skipped.

#### `drive status`

Show local changes since the last sync. Compares the current file state against the manifest.

```bash
drive status             # Human-readable output
drive status --porcelain # Machine-readable output (A/M/D prefixes)
```

**Output format (porcelain):**
```
A newly_added_file.txt
M modified_file.py
D deleted_file.log
```

---

### Information & Inspection

#### `drive info`

Display repository metadata and sync statistics.

```bash
drive info         # Basic repository information
drive info --scan  # Also count current local files
```

**Example output:**
```
Repository root: /home/user/my-project
Drive folder: My Project Backup (1AbC2dEfGhIjKlMnOpQrSt)
Metadata: /home/user/my-project/.drive
Manifest files: 42
Cached remote files: 42
Last manifest update: 2026-06-12T06:00:00Z
Ignore file: /home/user/my-project/.driveignore
```

#### `drive list`

List files in the linked remote Drive folder.

```bash
drive list               # List remote file names
drive list -l            # Long format: show sizes, timestamps, and file IDs
drive list --folders     # Include folders in the listing
drive list -l --folders  # Full listing with all metadata
```

---

### Cloning

#### `drive clone <folder_id> [path]`

Clone an existing Drive folder into a new local directory. Downloads all files, initializes the local repository metadata, and builds the manifest — ready for `drive push` and `drive pull`.

```bash
drive clone 1AbC2dEfGhIjKlMnOpQrSt                  # Clone into an auto-named directory
drive clone 1AbC2dEfGhIjKlMnOpQrSt ./my-local-copy   # Clone into a specific path
drive clone 1AbC2dEfGhIjKlMnOpQrSt --force            # Clone into a non-empty directory
```

**Notes:**
- The local directory name is derived from the Drive folder name (sanitized for filesystem safety).
- If the target directory already exists, a numeric suffix is appended (e.g., `my-project-1`).
- Google Workspace files are skipped with a notice.
- Remote `.drive/` metadata is skipped to preserve the new local repository state.

---

## Ignore Rules

Create a `.driveignore` file in the repository root to exclude files from all sync operations (`push`, `pull`, `status`, and manifest tracking). The syntax follows `.gitignore` conventions:

```text
# Directories (trailing slash)
node_modules/
.git/
__pycache__/

# Wildcard patterns
*.log
*.pyc
*.tmp

# Specific files
credentials.json
token.json

# Anchored patterns (relative to root)
/build/
/dist/

# Comments start with #
```

**Pattern matching rules:**
| Pattern        | Matches                                                     |
|----------------|-------------------------------------------------------------|
| `*.log`        | Any `.log` file at any depth                                |
| `venv/`        | Any directory named `venv` at any depth                     |
| `/build/`      | Only the `build/` directory at the repository root          |
| `docs/*.pdf`   | `.pdf` files directly inside `docs/`                        |
| `credentials.json` | Any file named `credentials.json` at any depth         |

**Built-in ignores** (always active, no `.driveignore` needed):

```text
.drive/  .git/  .agents/  .codex/  venv/  .venv/
__pycache__/  *.pyc  *.pyo  *.pyd  *.log
credentials.json  token.json
```

---

## Repository Metadata

Running `drive init` creates a `.drive/` directory in the repository root containing three JSON files:

| File              | Purpose                                                                                  |
|-------------------|------------------------------------------------------------------------------------------|
| `config.json`     | Stores the linked Drive folder ID, folder name, app version, and timestamps.             |
| `manifest.json`   | Tracks each synced file's path, SHA-256 hash, size, remote ID, and last sync timestamp.  |
| `cache.json`      | Caches the latest remote file listing to speed up subsequent operations.                  |

These files are local-only runtime metadata — they are automatically excluded from sync operations and should be added to `.gitignore`.

---

## Project Architecture

```text
drive-mirror/
├── drive                    # Shell entry point (chmod +x)
├── main.py                  # Python entry point (python main.py)
├── sync.py                  # Alias entry point (python sync.py)
├── pyproject.toml           # Package metadata and build config
├── requirements.txt         # Python dependencies
├── .gitignore
├── .driveignore
├── README.md
└── drive_mirror/            # Core package
    ├── __init__.py           # Package version (__version__)
    ├── cli.py                # Argument parser, subcommand routing, error handling
    ├── commands.py           # All command implementations (login, push, pull, etc.)
    ├── auth.py               # OAuth flow, token management, multi-account support
    ├── remote.py             # Google Drive API operations (upload, download, list, trash)
    ├── local.py              # Local filesystem scanning and SHA-256 hashing
    ├── metadata.py           # .drive/ JSON metadata read/write with atomic writes
    ├── ignore.py             # .driveignore pattern parsing and matching engine
    ├── models.py             # Data classes (RemoteIndex, IgnoreRule)
    ├── output.py             # Transfer progress display and formatting utilities
    ├── errors.py             # DriveMirrorError exception class
    └── constants.py          # Shared constants (scopes, MIME types, default ignores)
```

---

## Configuration Paths

| Path                                      | Description                        |
|-------------------------------------------|------------------------------------|
| `~/.config/drive-mirror/`                 | Global configuration directory     |
| `~/.config/drive-mirror/credentials.json` | OAuth client credentials           |
| `~/.config/drive-mirror/config.json`      | Global config (active account)     |
| `~/.config/drive-mirror/accounts/`        | Per-account OAuth token storage    |
| `./.drive/`                               | Per-repository metadata directory  |
| `./.driveignore`                          | Per-repository ignore rules        |

---

