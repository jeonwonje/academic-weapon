"""Scheduled jobs — daily Canvas sync + digest push via Telegram."""

from __future__ import annotations

import logging
from datetime import time, timezone, timedelta

from telegram.ext import Application

from src.config import settings

logger = logging.getLogger(__name__)

SGT = timezone(timedelta(hours=8))


async def _scheduled_sync_and_digest(context) -> None:
    """Run Canvas sync then push a daily digest to the configured chat."""
    chat_id = settings.telegram_chat_id
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID not set — skipping scheduled digest.")
        return

    logger.info("⏰ Scheduled sync + digest starting…")

    # 1. Sync Canvas + push to GitHub
    try:
        from src.github.orchestrator import sync_and_push

        result = await sync_and_push()
        summaries = result.sync_summaries
        total_downloaded = sum(
            len(s.get("files", {}).get("downloaded", []))
            for s in summaries
            if isinstance(s.get("files"), dict)
        )
        push_msg = f" | GitHub: {result.push_ok} pushed, {result.push_skipped} skipped, {result.push_failed} failed"
        logger.info("Sync complete: %d files downloaded across %d courses%s", total_downloaded, len(summaries), push_msg)
    except Exception as exc:
        logger.error("Scheduled sync failed: %s", exc)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Scheduled Canvas sync failed: {exc}",
            )
        except Exception:
            pass
        return

    # 2. Generate and push digest
    try:
        from src.llm.analyzer import Analyzer

        analyzer = Analyzer()
        digest = await analyzer.daily_digest()

        # Split long messages if needed
        max_len = 4096
        if len(digest) <= max_len:
            await context.bot.send_message(
                chat_id=chat_id,
                text=digest,
                parse_mode="Markdown",
            )
        else:
            # Send in chunks
            for i in range(0, len(digest), max_len):
                chunk = digest[i : i + max_len]
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        parse_mode="Markdown",
                    )
                except Exception:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                    )

        logger.info("Daily digest pushed to chat %s", chat_id)
    except Exception as exc:
        logger.error("Digest generation/push failed: %s", exc)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Daily digest generation failed: {exc}",
            )
        except Exception:
            pass


def register_scheduled_jobs(app: Application) -> None:
    """Register the daily sync+digest job on the bot's job queue."""
    job_queue = app.job_queue
    if job_queue is None:
        logger.error(
            "Job queue not available. Install python-telegram-bot[job-queue]."
        )
        return

    sync_time = time(
        hour=settings.sync_hour,
        minute=settings.sync_minute,
        tzinfo=SGT,
    )

    job_queue.run_daily(
        _scheduled_sync_and_digest,
        time=sync_time,
        name="daily_sync_digest",
    )

    logger.info(
        "📅 Scheduled daily sync + digest at %02d:%02d SGT",
        settings.sync_hour,
        settings.sync_minute,
    )
