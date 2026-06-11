# Drive Mirror

A small CLI for mirroring the current folder to a Google Drive folder.

## Setup

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create an OAuth desktop client in Google Cloud Console, enable the Google Drive API, and save the client JSON as `credentials.json` in this folder.

## Commands

From the project folder, run:

```bash
./drive login
./drive auth add <name>
./drive auth list
./drive auth use <name>
./drive auth current
./drive auth remove <name>
./drive init
./drive status
./drive push
./drive pull
./drive info
./drive list
```

If you install or symlink the executable into your `PATH`, the same commands work as `drive login`, `drive push`, and so on.

## Multi-Account Support

Drive Mirror supports authenticating and switching between multiple Google Drive accounts.

```bash
./drive auth add personal
./drive auth list
./drive auth use personal
./drive auth current
./drive auth remove default
```

Tokens for each account are stored securely in `~/.config/drive-mirror/accounts/`, and the active account configuration is saved in `~/.config/drive-mirror/config.json`.

## Project Layout

```text
drive_mirror/
  auth.py       OAuth and Google API client setup
  cli.py        Argument parsing and CLI error handling
  commands.py   Command workflows
  constants.py  Shared names, scopes, and MIME constants
  ignore.py     .driveignore parsing and matching
  local.py      Local scanning, SHA256 hashing, and status diffs
  metadata.py   .drive metadata read/write helpers
  remote.py     Google Drive folder, upload, download, and list operations
```

Root-level `drive`, `main.py`, and `sync.py` are only entry points.

## Repository Metadata

`drive init` creates a local `.drive/` directory:

- `.drive/config.json` stores the linked Drive folder id.
- `.drive/manifest.json` stores local SHA256 hashes and synced remote ids.
- `.drive/cache.json` stores the latest remote file listing.

These files are local runtime metadata and are ignored by synchronization.

## Ignore Rules

Add patterns to `.driveignore` to keep files out of push, pull, status, and manifests.

Example:

```text
venv/
.git/
__pycache__/
*.log
```

## Clone

Clone a Drive folder into a new local directory:

```bash
./drive clone <folder_id>
```

Or choose a target path:

```bash
./drive clone <folder_id> my-project
```
