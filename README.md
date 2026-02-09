# 🎯 Academic Weapon

NUS Canvas sync engine + GPT-powered Telegram bot that automatically downloads your course files daily, tracks deadlines, and answers questions about your modules.

## What it does

**Layer 1 — Canvas Sync Engine**
- Pulls files, assignments, announcements, calendar events, and modules from NUS Canvas
- Deduplicates downloads — only fetches new/updated files
- Preserves Canvas folder hierarchy locally
- Runs on a schedule or on-demand via Telegram

**Layer 2 — LLM Analysis via Telegram**
- Daily digest pushed to your chat (deadlines, announcements, study tips)
- `/deadlines` — sorted view of all upcoming due dates across modules
- `/summary CS2103` — GPT-generated course overview
- `/ask <anything>` — ask questions about your course content
- `/modules` — inline keyboard to pick which modules to sync
- Parses PDFs, DOCX, PPTX, HTML, and plain text files for LLM context

## Prerequisites

- Python 3.11+
- NUS Canvas account with API access
- OpenAI API key
- Telegram bot (created via [@BotFather](https://t.me/BotFather))

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-username/academic-weapon.git
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
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `TELEGRAM_BOT_TOKEN` | Message [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_CHAT_ID` | Message [@userinfobot](https://t.me/userinfobot) → it replies with your ID |

Optional settings:

| Variable | Default | Description |
|---|---|---|
| `CANVAS_API_URL` | `https://canvas.nus.edu.sg` | Canvas instance URL |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model to use |
| `DATA_DIR` | `./data` | Where synced files are stored |
| `SYNC_HOUR` | `6` | Daily sync hour (SGT, 24h) |
| `SYNC_MINUTE` | `0` | Daily sync minute |

### 3. Select your modules

Start the bot and use `/modules` in Telegram to pick which courses to sync. Only selected modules are downloaded and analysed. If nothing is selected, all active courses are synced.

### 4. Run

```bash
# Start the bot (handles Telegram + daily scheduled sync)
python -m src.main

# Or just sync Canvas without the bot
python scripts/sync_canvas.py
```

## Deployment

### Option A: systemd service (recommended for always-on servers)

```bash
sudo tee /etc/systemd/system/academic-weapon.service > /dev/null << 'EOF'
[Unit]
Description=Academic Weapon — NUS Canvas Telegram Bot
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
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable academic-weapon
sudo systemctl start academic-weapon

# Check status / logs
sudo systemctl status academic-weapon
journalctl -u academic-weapon -f
```

### Option B: tmux / screen (quick and easy)

```bash
tmux new -s weapon
source .venv/bin/activate
python -m src.main
# Ctrl+B, D to detach — bot keeps running
# tmux attach -t weapon to reattach
```

### Option C: Cron only (sync without bot)

If you just want the daily file sync without the Telegram bot:

```bash
crontab -e
```

Add:

```
0 6 * * * cd /home/YOUR_USERNAME/academic-weapon && .venv/bin/python scripts/sync_canvas.py >> logs/sync.log 2>&1
```

```bash
mkdir -p logs  # create log directory
```

### Option D: Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
CMD ["python", "-m", "src.main"]
```

```bash
docker build -t academic-weapon .
docker run -d --name weapon --env-file .env --restart unless-stopped academic-weapon
```

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Welcome message, list synced courses |
| `/modules` | Pick which modules to sync (inline keyboard) |
| `/sync` | Manually trigger Canvas data pull |
| `/digest` | GPT-generated daily digest |
| `/deadlines` | All upcoming deadlines, sorted by date |
| `/summary <course>` | Course overview (topics, assessment, key dates) |
| `/files <course>` | Recently synced files for a course |
| `/ask <question>` | Ask anything about your course content |
| `/help` | Show available commands |
| *(plain text)* | Auto-treated as `/ask` |

The bot also **auto-pushes** a daily digest at the configured time (default 6:00 AM SGT) to `TELEGRAM_CHAT_ID`.

## Project Structure

```
academic-weapon/
├── pyproject.toml              # Dependencies & project metadata
├── .env.example                # Template for environment config
├── scripts/
│   └── sync_canvas.py          # Standalone sync entry point (for cron)
├── src/
│   ├── main.py                 # Main entry point — bot + scheduler
│   ├── config.py               # Settings via pydantic-settings
│   ├── canvas/
│   │   ├── client.py           # Async Canvas API client
│   │   ├── models.py           # Pydantic models for API responses
│   │   ├── downloader.py       # File download with deduplication
│   │   ├── sync.py             # Sync orchestrator
│   │   └── course_selection.py # Module selection persistence
│   ├── llm/
│   │   ├── analyzer.py         # LLM analysis pipeline
│   │   ├── parser.py           # PDF/DOCX/PPTX/HTML text extraction
│   │   └── prompts.py          # Prompt templates
│   └── bot/
│       ├── telegram_bot.py     # Telegram command handlers
│       └── scheduler.py        # Daily digest push scheduler
└── data/                       # Synced files (gitignored)
    ├── courses.json
    ├── selected_courses.json
    ├── last_sync.json
    └── <Course Code>/
        ├── files/              # Downloaded course files
        ├── assignments.json
        ├── announcements.json
        ├── calendar_events.json
        ├── modules.json
        └── .sync_meta.json     # File dedup manifest
```

## How the sync works

1. Fetches all active courses from Canvas API
2. Filters to only your selected modules (via `/modules`)
3. For each course, pulls files, assignments, announcements, calendar events, and module structure
4. Files are deduplicated by comparing `updated_at` timestamps and file sizes against a local manifest — unchanged files are skipped
5. Canvas folder hierarchy is preserved on disk
6. Structured data (assignments, etc.) is saved as JSON for LLM consumption

## License

MIT
