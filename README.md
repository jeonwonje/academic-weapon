# Academic Weapon

NUS Canvas sync engine that automatically downloads your course files, pushes them to per-course GitHub repos, and provides a GPT-powered Telegram bot for deadlines, digests, and Q&A.

## What it does

**Canvas Sync Engine**
- Pulls files, assignments, announcements, calendar events, and modules from NUS Canvas
- Deduplicates downloads — only fetches new/updated files
- Preserves Canvas folder hierarchy locally
- Runs on a schedule or on-demand

**GitHub Auto-Push**
- Each course maps to its own GitHub repo (e.g. `ME2112` → `github.com/you/ME2112`)
- After every sync, changed files are committed and pushed automatically
- Handles first-time repo init, remote URL updates, and large file detection (>100MB)
- Configure mappings via the TUI or auto-generate from your Canvas courses

**Terminal UI (TUI)**
- Interactive dashboard showing all courses, sync status, and GitHub push status
- Configure which courses to push, edit repo names, toggle on/off
- Live sync + push progress view
- Launch with `canvas-tui`

**Telegram Bot**
- Daily digest pushed to your chat (deadlines, announcements, study tips)
- `/deadlines` — sorted view of all upcoming due dates across modules
- `/summary CS2103` — GPT-generated course overview
- `/ask <anything>` — ask questions about your course content
- `/sync` — trigger Canvas sync + GitHub push
- `/push` — push to GitHub without re-syncing
- `/repos` — show GitHub repo status
- Parses PDFs, DOCX, PPTX, HTML, and plain text files for LLM context

## Prerequisites

- Python 3.11+
- NUS Canvas account with API access
- GitHub CLI (`gh`) authenticated with `repo` scope
- OpenAI API key (for Telegram bot features)
- Telegram bot (optional, created via [@BotFather](https://t.me/BotFather))

## Setup

### 1. Clone and install

```bash
git clone https://github.com/jeonwonje/academic-weapon.git
cd academic-weapon
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | How to get it |
|---|---|
| `CANVAS_API_TOKEN` | Canvas → Settings → **+ New Access Token** |
| `GITHUB_OWNER` | Your GitHub username |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `TELEGRAM_BOT_TOKEN` | Message [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_CHAT_ID` | Message [@userinfobot](https://t.me/userinfobot) → it replies with your ID |

Optional settings:

| Variable | Default | Description |
|---|---|---|
| `CANVAS_API_URL` | `https://canvas.nus.edu.sg` | Canvas instance URL |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model to use |
| `GITHUB_COMMIT_PREFIX` | `[canvas-sync]` | Prefix for auto-commit messages |
| `DATA_DIR` | `./data` | Where synced files are stored |
| `SYNC_HOUR` | `6` | Daily sync hour (SGT, 24h) |
| `SYNC_MINUTE` | `0` | Daily sync minute |

### 3. Authenticate GitHub CLI

```bash
gh auth login
```

### 4. Create your course repos

The tool does **not** auto-create repos. Create them manually for each course you want to push:

```bash
gh repo create ME2112 --private
gh repo create CDE2310 --private
```

### 5. Configure and run

```bash
# Launch the TUI to configure course → repo mappings
canvas-tui

# Or start the Telegram bot (includes scheduled sync + push)
python -m src.main

# Or just sync + push without the bot
python scripts/sync_canvas.py
```

## TUI Usage

Launch with `canvas-tui` or `python -m src.tui.app`.

| Key | Action |
|---|---|
| `s` | Sync all (Canvas download + GitHub push) |
| `p` | Push all (GitHub only, no re-sync) |
| `c` | Configure course → repo mappings |
| `t` | Global settings (owner, commit prefix) |
| `q` | Quit |

In the config screen, press **Auto-Generate** to create mappings from your Canvas courses. Toggle checkboxes to enable/disable push per course. Edit the text field to change the target repo name.

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Welcome message, list synced courses |
| `/modules` | Pick which modules to sync (inline keyboard) |
| `/sync` | Trigger Canvas sync + GitHub push |
| `/push` | Push to GitHub without re-syncing |
| `/repos` | Show GitHub repo status for all courses |
| `/digest` | GPT-generated daily digest |
| `/deadlines` | All upcoming deadlines, sorted by date |
| `/summary <course>` | Course overview (topics, assessment, key dates) |
| `/files <course>` | Recently synced files for a course |
| `/ask <question>` | Ask anything about your course content |
| `/help` | Show available commands |
| *(plain text)* | Auto-treated as `/ask` |

## Deployment

### systemd (recommended for always-on servers)

```bash
sudo tee /etc/systemd/system/academic-weapon.service > /dev/null << 'EOF'
[Unit]
Description=Academic Weapon — NUS Canvas Sync + GitHub Push
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/academic-weapon
ExecStart=/home/YOUR_USERNAME/academic-weapon/.venv/bin/python -m src.main
Restart=on-failure
RestartSec=10
EnvironmentFile=/home/YOUR_USERNAME/academic-weapon/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now academic-weapon
```

### Cron (sync + push without bot)

```
0 6 * * * cd /home/YOUR_USERNAME/academic-weapon && .venv/bin/python scripts/sync_canvas.py >> logs/sync.log 2>&1
```

### Docker

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
CMD ["python", "-m", "src.main"]
```

## Project Structure

```
academic-weapon/
├── pyproject.toml
├── .env.example
├── scripts/
│   └── sync_canvas.py          # Standalone sync + push (for cron)
├── src/
│   ├── main.py                 # Main entry point — bot + scheduler
│   ├── config.py               # Settings via pydantic-settings
│   ├── canvas/
│   │   ├── client.py           # Async Canvas API client
│   │   ├── models.py           # Pydantic models for API responses
│   │   ├── downloader.py       # File download with deduplication
│   │   ├── sync.py             # Canvas sync orchestrator
│   │   └── course_selection.py # Module selection persistence
│   ├── github/
│   │   ├── models.py           # RepoMapping, GitHubConfig, PushResult
│   │   ├── config_manager.py   # GitHub config CRUD (data/github_config.json)
│   │   ├── pusher.py           # Git init, commit, push per course
│   │   └── orchestrator.py     # sync_and_push() — Canvas sync then GitHub push
│   ├── llm/
│   │   ├── analyzer.py         # LLM analysis pipeline
│   │   ├── parser.py           # PDF/DOCX/PPTX/HTML text extraction
│   │   └── prompts.py          # Prompt templates
│   ├── bot/
│   │   ├── telegram_bot.py     # Telegram command handlers
│   │   └── scheduler.py        # Daily sync + push + digest scheduler
│   └── tui/
│       ├── app.py              # Textual TUI main app
│       └── screens/
│           ├── dashboard.py    # Course overview table
│           ├── config.py       # Repo mapping editor
│           ├── sync.py         # Live sync + push progress
│           └── settings.py     # Global settings editor
└── data/                       # Synced files (gitignored)
    ├── courses.json
    ├── github_config.json      # GitHub push configuration
    ├── selected_courses.json
    └── <COURSE_CODE>/
        ├── files/              # Downloaded course files
        ├── assignments.json
        ├── announcements.json
        └── modules.json
```

## How it works

1. Fetches all active courses from Canvas API
2. Filters to your selected modules (via `/modules` or TUI)
3. For each course, pulls files, assignments, announcements, calendar events, and modules
4. Files are deduplicated by comparing timestamps and sizes against a local manifest
5. After sync, each enabled course directory is committed and pushed to its GitHub repo
6. Structured data (assignments, etc.) is saved as JSON

## License

MIT
