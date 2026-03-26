"""Telegram bot — command handlers for the Academic Weapon assistant."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from src.canvas.course_selection import (
    has_selection,
    load_course_registry,
    load_selected_course_ids,
    select_all,
    clear_selection,
    toggle_course,
)
from src.config import settings
from src.llm.analyzer import Analyzer

logger = logging.getLogger(__name__)

# Telegram message length limit
MAX_MSG_LEN = 4096

analyzer = Analyzer()


def _truncate(text: str, limit: int = MAX_MSG_LEN) -> str:
    """Truncate text to fit Telegram's message limit."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n\n… _(truncated)_"


async def _safe_reply(update: Update, text: str, parse_mode: str | None = ParseMode.MARKDOWN) -> None:
    """Reply with fallback to plain text if Markdown parsing fails."""
    try:
        await update.message.reply_text(_truncate(text), parse_mode=parse_mode)
    except Exception:
        # Telegram can reject malformed Markdown — fall back to plain text
        await update.message.reply_text(_truncate(text), parse_mode=None)


# ── Command Handlers ────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message."""
    courses = analyzer.list_courses()
    course_list = "\n".join(f"  • `{c}`" for c in courses) if courses else "  _None synced yet. Run /sync first._"

    selected = load_selected_course_ids()
    if selected:
        sel_info = f"\n📌 *Selected modules:* {len(selected)} of {len(courses)} courses"
    else:
        sel_info = "\n⚠️ _No modules selected — syncing ALL courses. Use /modules to pick._"

    await _safe_reply(
        update,
        f"🎯 *Academic Weapon — Online*\n\n"
        f"Your NUS Canvas AI assistant.\n\n"
        f"*Synced courses:*\n{course_list}{sel_info}\n\n"
        f"*Commands:*\n"
        f"/modules — Select which modules to sync\n"
        f"/digest — Daily academic digest\n"
        f"/deadlines — All upcoming deadlines\n"
        f"/summary `<course>` — Course overview\n"
        f"/files `<course>` — Recent files\n"
        f"/ask `<question>` — Ask anything about your courses\n"
        f"/sync — Pull latest data from Canvas + push to GitHub\n"
        f"/push — Push to GitHub without re-syncing\n"
        f"/repos — Show GitHub repo status\n"
        f"/help — Show this message",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    await cmd_start(update, context)


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /digest — generate daily digest."""
    await update.message.reply_text("⏳ Generating your daily digest…")
    try:
        result = await analyzer.daily_digest()
        await _safe_reply(update, result)
    except Exception as exc:
        logger.error("Digest failed: %s", exc)
        await _safe_reply(update, f"❌ Failed to generate digest: {exc}", parse_mode=None)


async def cmd_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /deadlines — list upcoming deadlines."""
    await update.message.reply_text("⏳ Fetching deadlines…")
    try:
        result = await analyzer.deadlines()
        await _safe_reply(update, result)
    except Exception as exc:
        logger.error("Deadlines failed: %s", exc)
        await _safe_reply(update, f"❌ Failed to fetch deadlines: {exc}", parse_mode=None)


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /summary <course_code> — course overview."""
    if not context.args:
        courses = analyzer.list_courses()
        course_list = ", ".join(f"`{c}`" for c in courses) if courses else "_none_"
        await _safe_reply(
            update,
            f"Usage: /summary `<course_code>`\n\nAvailable: {course_list}",
        )
        return

    course_code = " ".join(context.args)
    await update.message.reply_text(f"⏳ Summarising {course_code}…")
    try:
        result = await analyzer.course_summary(course_code)
        await _safe_reply(update, result)
    except Exception as exc:
        logger.error("Summary failed: %s", exc)
        await _safe_reply(update, f"❌ Failed: {exc}", parse_mode=None)


async def cmd_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /files <course_code> — list recently synced files."""
    if not context.args:
        courses = analyzer.list_courses()
        course_list = ", ".join(f"`{c}`" for c in courses) if courses else "_none_"
        await _safe_reply(
            update,
            f"Usage: /files `<course_code>`\n\nAvailable: {course_list}",
        )
        return

    course_code = " ".join(context.args)
    files = analyzer.list_recent_files(course_code)

    if not files:
        await _safe_reply(update, f"📂 No files found for `{course_code}`.")
        return

    lines = [f"📂 *Recent files — {course_code}*\n"]
    for f in files:
        name = f["name"]
        updated = f["updated"][:10] if f["updated"] else "?"
        ftype = f["type"].split("/")[-1] if f["type"] else "?"
        lines.append(f"  • `{name}` ({ftype}) — {updated}")

    await _safe_reply(update, "\n".join(lines))


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ask <question> — free-form question."""
    if not context.args:
        await _safe_reply(
            update,
            "Usage: /ask `<your question>`\n\n"
            "Examples:\n"
            "  /ask What's due this week?\n"
            "  /ask Summarise lecture 5 for CS2103\n"
            "  /ask What topics are covered in week 7?",
        )
        return

    question = " ".join(context.args)
    await update.message.reply_text(f"🤔 Thinking about: _{question}_…", parse_mode=ParseMode.MARKDOWN)
    try:
        result = await analyzer.answer_query(question)
        await _safe_reply(update, result)
    except Exception as exc:
        logger.error("Query failed: %s", exc)
        await _safe_reply(update, f"❌ Failed: {exc}", parse_mode=None)


# ── Module Selection ────────────────────────────────────────────────────

def _build_modules_keyboard() -> InlineKeyboardMarkup | None:
    """Build an inline keyboard with all Canvas courses as toggle buttons."""
    courses = load_course_registry()
    if not courses:
        return None

    selected = load_selected_course_ids()
    buttons: list[list[InlineKeyboardButton]] = []

    for c in courses:
        cid = c.get("id", 0)
        code = c.get("course_code", "") or c.get("name", f"Course {cid}")
        check = "✅" if cid in selected else "⬜"
        buttons.append([
            InlineKeyboardButton(
                text=f"{check} {code}",
                callback_data=f"toggle_{cid}",
            )
        ])

    # Action row
    buttons.append([
        InlineKeyboardButton("✅ Select All", callback_data="select_all"),
        InlineKeyboardButton("❌ Clear All", callback_data="clear_all"),
    ])
    buttons.append([
        InlineKeyboardButton("🔄 Done — Run Sync", callback_data="done_sync"),
    ])

    return InlineKeyboardMarkup(buttons)


async def cmd_modules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /modules — show inline keyboard to select courses."""
    courses = load_course_registry()

    if not courses:
        await _safe_reply(
            update,
            "📭 No course list found. Running a quick Canvas fetch…",
        )
        # Fetch course list from Canvas
        try:
            from src.canvas.client import CanvasClient
            import json

            async with CanvasClient() as client:
                fetched = await client.list_courses()
                settings.data_dir.mkdir(parents=True, exist_ok=True)
                (settings.data_dir / "courses.json").write_text(
                    json.dumps([c.model_dump() for c in fetched], indent=2, default=str)
                )
            courses = load_course_registry()
        except Exception as exc:
            await _safe_reply(update, f"❌ Failed to fetch courses: {exc}", parse_mode=None)
            return

    if not courses:
        await _safe_reply(update, "❌ No active courses found on Canvas.")
        return

    selected = load_selected_course_ids()
    count = len(selected)
    total = len(courses)
    header = (
        f"📚 *Select your modules* ({count}/{total} selected)\n\n"
        f"Tap a module to toggle it on/off.\n"
        f"Only selected modules will be synced and analysed."
    )

    keyboard = _build_modules_keyboard()
    await update.message.reply_text(header, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def handle_module_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses for module selection."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("toggle_"):
        course_id = int(data.split("_", 1)[1])
        now_selected = toggle_course(course_id)
        action = "selected" if now_selected else "deselected"
        logger.info("Course %d %s", course_id, action)

    elif data == "select_all":
        courses = load_course_registry()
        select_all([c["id"] for c in courses])

    elif data == "clear_all":
        clear_selection()
        # Re-create empty selection so has_selection() returns True
        from src.canvas.course_selection import save_selected_course_ids
        save_selected_course_ids(set())

    elif data == "done_sync":
        selected = load_selected_course_ids()
        if not selected:
            await query.edit_message_text(
                "⚠️ No modules selected. Use /modules to pick at least one, "
                "or all courses will be synced."
            )
            return
        await query.edit_message_text(
            f"✅ *{len(selected)} modules selected.* Running sync…",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Trigger sync
        try:
            from src.canvas.sync import run_sync
            summaries = await run_sync()
            lines = [f"✅ *Sync complete — {len(summaries)} courses*\n"]
            for s in summaries:
                course = s.get("course", "?")
                files = s.get("files", {})
                if isinstance(files, dict) and "error" not in files:
                    dl = len(files.get("downloaded", []))
                    lines.append(f"  • *{course}*: {dl} new files")
                else:
                    lines.append(f"  • *{course}*: {files}")
            await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        except Exception as exc:
            await query.message.reply_text(f"❌ Sync failed: {exc}")
        return

    # Refresh the keyboard to show updated toggles
    selected = load_selected_course_ids()
    courses = load_course_registry()
    count = len(selected)
    total = len(courses)
    header = (
        f"📚 *Select your modules* ({count}/{total} selected)\n\n"
        f"Tap a module to toggle it on/off.\n"
        f"Only selected modules will be synced and analysed."
    )
    keyboard = _build_modules_keyboard()
    await query.edit_message_text(header, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sync — manually trigger Canvas sync + GitHub push."""
    await update.message.reply_text("🔄 Starting Canvas sync… this may take a few minutes.")
    try:
        from src.github.orchestrator import sync_and_push

        result = await sync_and_push()

        lines = ["✅ *Sync complete!*\n"]
        for s in result.sync_summaries:
            course = s.get("course", "?")
            files = s.get("files", {})
            if isinstance(files, dict) and "error" not in files:
                dl = len(files.get("downloaded", []))
                sk = len(files.get("skipped", []))
                fa = len(files.get("failed", []))
                lines.append(
                    f"  *{course}*: {dl} new, {sk} unchanged, {fa} failed | "
                    f"{s.get('assignments_count', 0)} assignments, "
                    f"{s.get('announcements_count', 0)} announcements"
                )
            else:
                lines.append(f"  *{course}*: {files}")

        if result.push_results:
            lines.append(f"\n📤 *GitHub push:* {result.push_ok} pushed, {result.push_skipped} skipped, {result.push_failed} failed")
            for pr in result.push_results:
                if pr.status == "failed":
                    lines.append(f"  ❌ {pr.course_code}: {pr.error}")

        await _safe_reply(update, "\n".join(lines))
    except Exception as exc:
        logger.error("Sync failed: %s", exc)
        await _safe_reply(update, f"❌ Sync failed: {exc}", parse_mode=None)


async def cmd_push(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /push — manually trigger GitHub push without re-syncing."""
    await update.message.reply_text("📤 Pushing to GitHub…")
    try:
        from src.github.pusher import push_all

        results = await push_all()
        if not results:
            await _safe_reply(update, "ℹ️ No GitHub mappings configured. Use the TUI (`canvas-tui`) to set up repos.")
            return

        lines = ["📤 *GitHub push complete!*\n"]
        for r in results:
            if r.status == "ok":
                lines.append(f"  ✅ *{r.course_code}*: {r.files_changed} files pushed")
            elif r.status == "skipped":
                lines.append(f"  ⏭ *{r.course_code}*: no changes")
            else:
                lines.append(f"  ❌ *{r.course_code}*: {r.error}")

        await _safe_reply(update, "\n".join(lines))
    except Exception as exc:
        logger.error("Push failed: %s", exc)
        await _safe_reply(update, f"❌ Push failed: {exc}", parse_mode=None)


async def cmd_repos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /repos — show GitHub repo status for all configured courses."""
    from src.github.config_manager import load_config

    config = load_config()
    if not config.mappings:
        await _safe_reply(update, "ℹ️ No GitHub repos configured. Use the TUI (`canvas-tui`) to set up repos.")
        return

    lines = ["📦 *GitHub Repos*\n"]
    for m in config.mappings:
        status = "✅" if m.enabled else "⏸"
        push_info = m.last_push_at[:10] if m.last_push_at else "Never"
        lines.append(f"  {status} *{m.course_code}* → `{m.github_owner}/{m.github_repo}` (last push: {push_info})")

    await _safe_reply(update, "\n".join(lines))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages (no command) — treat as /ask."""
    question = update.message.text.strip()
    if not question:
        return

    await update.message.reply_text(f"🤔 _{question}_…", parse_mode=ParseMode.MARKDOWN)
    try:
        result = await analyzer.answer_query(question)
        await _safe_reply(update, result)
    except Exception as exc:
        logger.error("Text query failed: %s", exc)
        await _safe_reply(update, f"❌ Failed: {exc}", parse_mode=None)


def build_application() -> Application:
    """Build and configure the Telegram bot application."""
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Create a bot via @BotFather on Telegram."
        )

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("modules", cmd_modules))
    app.add_handler(CallbackQueryHandler(handle_module_callback))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("deadlines", cmd_deadlines))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("files", cmd_files))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler("push", cmd_push))
    app.add_handler(CommandHandler("repos", cmd_repos))

    # Plain text → treat as question
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
