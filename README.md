# 🎯 Academic Weapon - Canvas Auto-Sync

Automatically syncs and updates files from Canvas, with intelligent deduplication to avoid re-downloading unchanged files.

## Features

- ✅ Pulls files, assignments, announcements, calendar events from Canvas
- ✅ Deduplicates downloads — only fetches new/updated files
- ✅ Preserves Canvas folder hierarchy locally
- ✅ Can be run manually or scheduled via cron

## Setup

### 1. Clone and Install

```bash
cd canvas
python3 -m venv .venv
source .venv/bin/activate  # On Linux/Mac
# .venv\Scripts\activate  # On Windows
pip install -e .
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Canvas API token:
- Go to Canvas → Settings → + New Access Token
- Copy the token and paste it in `.env`

### 3. Run the Sync

```bash
python scripts/sync_canvas.py
```

## Scheduling Automatic Syncs

### Option A: Cron (Linux/Mac)

```bash
crontab -e
```

Add this line to sync daily at 6 AM:
```
0 6 * * * cd /path/to/canvas && .venv/bin/python scripts/sync_canvas.py >> logs/sync.log 2>&1
```

### Option B: Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 6 AM)
4. Action: Start a program
   - Program: `C:\path\to\canvas\.venv\Scripts\python.exe`
   - Arguments: `scripts/sync_canvas.py`
   - Start in: `C:\path\to\canvas`

## Data Structure

All synced data is stored in the `data/` directory:

```
data/
├── courses.json              # List of your courses
├── last_sync.json            # Last sync timestamp
└── <Course Code>/
    ├── files/                # Downloaded course files
    ├── assignments.json
    ├── announcements.json
    ├── calendar_events.json
    ├── modules.json
    └── .sync_meta.json       # File dedup manifest
```

## How Deduplication Works

1. Each file's metadata (updated_at timestamp, size, checksum) is stored in `.sync_meta.json`
2. Before downloading, the script checks if the file has changed
3. Only new or modified files are downloaded
4. Deleted files on Canvas are optionally removed locally (configurable)

## License

MIT
