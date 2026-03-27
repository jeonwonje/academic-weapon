"""Standalone Canvas sync script - can be run manually or via cron."""
import asyncio
import sys
import io
import logging
from pathlib import Path

# Force UTF-8 output on Windows to avoid cp1252 UnicodeEncodeError
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

handlers = [logging.StreamHandler()]
try:
    handlers.append(
        logging.FileHandler(log_dir / "sync.log", encoding="utf-8")
    )
except PermissionError:
    from datetime import datetime as _dt
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    handlers.append(
        logging.FileHandler(log_dir / f"sync_{ts}.log", encoding="utf-8")
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
)

from src.canvas.sync import CanvasSync
from src.cli import prompt_course_selection


async def main():
    """Main sync function with interactive course selection."""
    try:
        syncer = CanvasSync()

        # 1. Fetch available courses from Canvas
        print("Fetching course list from Canvas...")
        courses = await syncer.fetch_courses()
        print(f"Found {len(courses)} courses on Canvas.\n")

        # 2. Show interactive picker (remembers previous choices)
        course_dicts = [c.model_dump() for c in courses]
        selected_ids = prompt_course_selection(course_dicts, syncer.data_dir)

        if not selected_ids:
            print("\nNothing to sync. Exiting.")
            return

        # 3. Sync only the selected courses
        results = await syncer.sync_all(selected_course_ids=selected_ids)

        if results["failed_count"] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nSync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
