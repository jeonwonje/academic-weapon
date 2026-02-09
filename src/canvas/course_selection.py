"""Persistent course selection — tracks which modules the user is taking this semester."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


def _selection_path() -> Path:
    """Path to the selected_courses.json file."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "selected_courses.json"


def load_selected_course_ids() -> set[int]:
    """Load the set of selected Canvas course IDs from disk."""
    path = _selection_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(data.get("selected_ids", []))
    except Exception as exc:
        logger.warning("Failed to load course selection: %s", exc)
        return set()


def save_selected_course_ids(ids: set[int]) -> None:
    """Persist selected course IDs to disk."""
    path = _selection_path()
    path.write_text(json.dumps({"selected_ids": sorted(ids)}, indent=2))


def load_course_registry() -> list[dict]:
    """Load the full course list from the last Canvas fetch.

    Returns a list of dicts with keys: id, name, course_code.
    """
    path = settings.data_dir / "courses.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def toggle_course(course_id: int) -> bool:
    """Toggle a course on/off. Returns True if it's now selected, False if deselected."""
    selected = load_selected_course_ids()
    if course_id in selected:
        selected.discard(course_id)
        result = False
    else:
        selected.add(course_id)
        result = True
    save_selected_course_ids(selected)
    return result


def is_selected(course_id: int) -> bool:
    """Check if a course is currently selected."""
    return course_id in load_selected_course_ids()


def has_selection() -> bool:
    """Return True if the user has made any course selection."""
    return _selection_path().exists() and bool(load_selected_course_ids())


def select_all(course_ids: list[int]) -> None:
    """Select all courses at once."""
    save_selected_course_ids(set(course_ids))


def clear_selection() -> None:
    """Clear all selections (reverts to syncing everything)."""
    path = _selection_path()
    if path.exists():
        path.unlink()
