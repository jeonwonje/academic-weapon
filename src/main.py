"""Main entry point — runs Canvas sync + GitHub push."""

from __future__ import annotations

import asyncio
import logging
import sys

from src.canvas.sync import run_sync
from src.config import settings


def main() -> None:
    """Run a Canvas sync and push to GitHub."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)

    if not settings.canvas_api_token:
        logger.error(
            "CANVAS_API_TOKEN is not set.\n"
            "Copy .env.example → .env and fill in your token."
        )
        sys.exit(1)

    logger.info("Academic Weapon — Canvas sync starting…")
    logger.info("   Canvas: %s", settings.canvas_api_url)
    logger.info("   Data dir: %s", settings.data_dir.resolve())

    try:
        from src.github.orchestrator import sync_and_push

        result = asyncio.run(sync_and_push())
        total = len(result.sync_summaries)
        logger.info("Sync complete: %d courses synced, GitHub: %d pushed, %d skipped, %d failed",
                     total, result.push_ok, result.push_skipped, result.push_failed)
    except Exception as exc:
        logger.error("Sync failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
