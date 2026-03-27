# 🚀 Quick Start Guide

## Step 1: Get Your Canvas API Token

1. Log in to Canvas (https://canvas.nus.edu.sg or your institution's Canvas URL)
2. Click on **Account** (left sidebar) → **Settings**
3. Scroll down to **Approved Integrations**
4. Click **+ New Access Token**
5. Give it a name (e.g., "Canvas Sync") and click **Generate Token**
6. **Copy the token** (you won't be able to see it again!)

## Step 2: Setup the Project

### On Linux/Mac:

```bash
# Run the setup script
./setup.sh

# Or manual setup:
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### On Windows:

```cmd
REM Run the setup script
setup.bat

REM Or manual setup:
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Step 3: Configure Your API Token

Edit the `.env` file and add your Canvas API token:

```bash
# Open .env in your favorite editor
nano .env
# or
code .env
# or
vim .env
```

Update these values:
```
CANVAS_API_TOKEN=your_actual_token_here
CANVAS_API_URL=https://canvas.nus.edu.sg
```

## Step 4: Run Your First Sync

```bash
# Make sure virtual environment is activated
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Run the sync
python scripts/sync_canvas.py
```

The script will:
- ✅ Fetch all your active courses
- ✅ Download new and updated files
- ✅ Save assignments, announcements, and calendar events
- ✅ Skip unchanged files (no re-downloading!)
- ✅ Organize everything in the `data/` directory

## Step 4.5: Open Readable Pages

After syncing, you can open local HTML pages for quick viewing:

```bash
# Announcements
python scripts/view_announcements.py

# Assignments (due dates + details)
python scripts/view_assignments.py
```

## Step 5: Schedule Automatic Syncs

### Linux/Mac (using cron):

```bash
# Create logs directory
mkdir -p logs

# Edit crontab
crontab -e

# Add this line to sync daily at 6 AM:
0 6 * * * cd /mnt/c/Users/jeonw/Desktop/canvas && .venv/bin/python scripts/sync_canvas.py >> logs/sync.log 2>&1
```

### Windows (using Task Scheduler):

1. Open **Task Scheduler**
2. Click **Create Basic Task**
3. Name: "Canvas Auto-Sync"
4. Trigger: **Daily** at **6:00 AM**
5. Action: **Start a program**
   - Program: `C:\Users\jeonw\Desktop\canvas\.venv\Scripts\python.exe`
   - Arguments: `scripts\sync_canvas.py`
   - Start in: `C:\Users\jeonw\Desktop\canvas`
6. Click **Finish**

## What Gets Downloaded?

After syncing, check the `data/` directory:

```
data/
├── courses.json                    # List of all your courses
├── last_sync.json                  # Last sync summary and stats
└── <Course Code>/                  # One folder per course
    ├── files/                      # All course files (organized by folder)
    │   ├── Lectures/
    │   ├── Tutorials/
    │   └── ...
    ├── assignments.json            # All assignments with due dates
    ├── announcements.json          # Course announcements
    ├── calendar_events.json        # Calendar events
    ├── modules.json                # Course modules/structure
    └── .sync_meta.json             # File metadata (for deduplication)
```

## Troubleshooting

### "CANVAS_API_TOKEN not found"
- Make sure you created the `.env` file
- Make sure you added your actual token (not the placeholder)
- Token should have no quotes around it

### "401 Unauthorized"
- Your API token is invalid or expired
- Generate a new token from Canvas Settings

### "Connection refused" or "Network error"
- Check your internet connection
- Verify the CANVAS_API_URL in `.env` is correct

### Files not downloading
- Check if files are locked or hidden in Canvas
- Check logs for specific error messages
- Make sure you have enough disk space

## Advanced Usage

See [examples/usage_examples.py](examples/usage_examples.py) for:
- Syncing specific courses only
- Using the Canvas API client directly
- Downloading specific file types only
- Programmatic integration with your own scripts

## Need Help?

- Check the logs in `logs/sync.log`
- Review the last sync results in `data/last_sync.json`
- Make sure your Canvas API token has proper permissions

---

Happy syncing! 🎯
