"""Main entry point — starts the Telegram bot with scheduled jobs."""

from __future__ import annotations

import logging
import sys

from src.bot.telegram_bot import build_application
from src.bot.scheduler import register_scheduled_jobs
from src.config import settings


def main() -> None:
    """Launch the Academic Weapon bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger(__name__)

    # Validate required config
    missing: list[str] = []
    if not settings.canvas_api_token:
        missing.append("CANVAS_API_TOKEN")
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")

    if missing:
        logger.error(
            "Missing required environment variables: %s\n"
            "Copy .env.example → .env and fill in your tokens.",
            ", ".join(missing),
        )
        sys.exit(1)

    # Build app
    app = build_application()

    # Register scheduled jobs (daily sync + digest)
    register_scheduled_jobs(app)

    logger.info("🎯 Academic Weapon bot starting… (Ctrl+C to stop)")
    logger.info("   Canvas: %s", settings.canvas_api_url)
    logger.info("   Data dir: %s", settings.data_dir.resolve())
    logger.info("   LLM model: %s", settings.openai_model)

    if settings.telegram_chat_id:
        logger.info("   Daily digest → chat %s at %02d:%02d SGT",
                     settings.telegram_chat_id, settings.sync_hour, settings.sync_minute)
    else:
        logger.warning("   TELEGRAM_CHAT_ID not set — daily digest push disabled.")

    # Run the bot (blocking)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
