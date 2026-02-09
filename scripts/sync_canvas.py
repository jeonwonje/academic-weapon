#!/usr/bin/env python3
"""Standalone sync script — use this in cron or run manually.

Usage:
    python scripts/sync_canvas.py

Cron example (daily at 6 AM):
    0 6 * * * cd /home/jeon-wsl/academic-weapon && /path/to/venv/bin/python scripts/sync_canvas.py >> logs/sync.log 2>&1
"""

import sys
from pathlib import Path

# Ensure the project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.canvas.sync import main  # noqa: E402

if __name__ == "__main__":
    main()
