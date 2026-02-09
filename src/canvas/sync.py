"""Canvas sync orchestrator — pulls everything for all courses."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.canvas.client import CanvasClient
from src.canvas.course_selection import has_selection, load_selected_course_ids
from src.canvas.downloader import FileDownloader
from src.canvas.models import Course
from src.config import settings

logger = logging.getLogger(__name__)


def _dump_json(path: Path, data: list[dict[str, Any]]) -> None:
    """Write a list of dicts to a JSON file."""
    path.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False))


async def sync_course(client: CanvasClient, course: Course) -> dict[str, Any]:
    """Sync a single course's files + metadata. Returns a summary dict."""
    label = course.label
    course_dir = settings.course_dir(label)
    summary: dict[str, Any] = {"course": label, "course_id": course.id}

    logger.info("── Syncing course: %s (id=%d) ──", label, course.id)

    # 1. Files ---------------------------------------------------------------
    try:
        files = await client.list_files(course.id)
        folders = await client.list_folders(course.id)
        dl = FileDownloader(client, course_dir)
        file_result = await dl.sync_files(files, folders)
        summary["files"] = file_result
        logger.info(
            "  Files: %d downloaded, %d skipped, %d failed",
            len(file_result["downloaded"]),
            len(file_result["skipped"]),
            len(file_result["failed"]),
        )
    except Exception as exc:
        logger.error("  Files sync failed: %s", exc)
        summary["files"] = {"error": str(exc)}

    # 2. Assignments ---------------------------------------------------------
    try:
        assignments = await client.list_assignments(course.id)
        _dump_json(
            course_dir / "assignments.json",
            [a.model_dump() for a in assignments],
        )
        summary["assignments_count"] = len(assignments)
        logger.info("  Assignments: %d", len(assignments))
    except Exception as exc:
        logger.error("  Assignments sync failed: %s", exc)
        summary["assignments_count"] = 0

    # 3. Announcements -------------------------------------------------------
    try:
        announcements = await client.list_announcements(
            [f"course_{course.id}"]
        )
        _dump_json(
            course_dir / "announcements.json",
            [a.model_dump() for a in announcements],
        )
        summary["announcements_count"] = len(announcements)
        logger.info("  Announcements: %d", len(announcements))
    except Exception as exc:
        logger.error("  Announcements sync failed: %s", exc)
        summary["announcements_count"] = 0

    # 4. Calendar events (both types) ----------------------------------------
    try:
        ctx = [f"course_{course.id}"]
        events = await client.list_calendar_events(ctx, event_type="event")
        assignment_events = await client.list_calendar_events(
            ctx, event_type="assignment"
        )
        all_events = events + assignment_events
        _dump_json(
            course_dir / "calendar_events.json",
            [e.model_dump() for e in all_events],
        )
        summary["calendar_events_count"] = len(all_events)
        logger.info("  Calendar events: %d", len(all_events))
    except Exception as exc:
        logger.error("  Calendar events sync failed: %s", exc)
        summary["calendar_events_count"] = 0

    # 5. Modules -------------------------------------------------------------
    try:
        modules = await client.list_modules(course.id)
        _dump_json(
            course_dir / "modules.json",
            [m.model_dump() for m in modules],
        )
        summary["modules_count"] = len(modules)
        logger.info("  Modules: %d", len(modules))
    except Exception as exc:
        logger.error("  Modules sync failed: %s", exc)
        summary["modules_count"] = 0

    return summary


async def run_sync() -> list[dict[str, Any]]:
    """Run a full sync of all active courses. Returns a list of per-course summaries."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not settings.canvas_api_token:
        raise RuntimeError(
            "CANVAS_API_TOKEN is not set. "
            "Generate one at Canvas → Settings → New Access Token."
        )

    logger.info("Starting Canvas sync at %s", datetime.now(timezone.utc).isoformat())

    async with CanvasClient() as client:
        courses = await client.list_courses(include=["syllabus_body"])
        logger.info("Found %d active courses", len(courses))

        # Write a courses index
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _dump_json(
            settings.data_dir / "courses.json",
            [c.model_dump() for c in courses],
        )

        # Filter to selected courses if the user has made a selection
        if has_selection():
            selected_ids = load_selected_course_ids()
            courses_to_sync = [c for c in courses if c.id in selected_ids]
            logger.info(
                "Filtering to %d selected courses (out of %d total)",
                len(courses_to_sync),
                len(courses),
            )
        else:
            courses_to_sync = courses
            logger.info("No module selection — syncing all %d courses", len(courses))

        # Sync each course sequentially to respect rate limits
        summaries: list[dict[str, Any]] = []
        for course in courses_to_sync:
            s = await sync_course(client, course)
            summaries.append(s)

    # Write overall sync summary
    sync_report = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "courses": summaries,
    }
    _dump_json(settings.data_dir / "last_sync.json", [sync_report])
    logger.info("Sync complete. Summary written to %s", settings.data_dir / "last_sync.json")

    return summaries


def main() -> None:
    """CLI entry point for `sync-canvas` command."""
    asyncio.run(run_sync())


if __name__ == "__main__":
    main()
