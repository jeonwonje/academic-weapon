"""CRUD for GitHub push configuration — persisted to data/github_config.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import settings
from src.github.models import GitHubConfig, RepoMapping

logger = logging.getLogger(__name__)


def _config_path() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "github_config.json"


def load_config() -> GitHubConfig:
    path = _config_path()
    if not path.exists():
        return GitHubConfig(owner=settings.github_owner)
    try:
        data = json.loads(path.read_text())
        return GitHubConfig.model_validate(data)
    except Exception as exc:
        logger.warning("Failed to load GitHub config: %s", exc)
        return GitHubConfig(owner=settings.github_owner)


def save_config(config: GitHubConfig) -> None:
    path = _config_path()
    path.write_text(config.model_dump_json(indent=2))


def get_mapping(course_code: str) -> RepoMapping | None:
    config = load_config()
    for m in config.mappings:
        if m.course_code == course_code:
            return m
    return None


def upsert_mapping(mapping: RepoMapping) -> None:
    config = load_config()
    for i, m in enumerate(config.mappings):
        if m.course_code == mapping.course_code:
            config.mappings[i] = mapping
            save_config(config)
            return
    config.mappings.append(mapping)
    save_config(config)


def toggle_mapping(course_code: str) -> bool | None:
    """Toggle a mapping on/off. Returns new enabled state, or None if not found."""
    config = load_config()
    for m in config.mappings:
        if m.course_code == course_code:
            m.enabled = not m.enabled
            save_config(config)
            return m.enabled
    return None


def auto_generate_mappings(courses: list[dict]) -> list[RepoMapping]:
    """Generate default mappings from a course list (from courses.json).

    Only creates mappings for courses that don't already have one.
    """
    config = load_config()
    existing = {m.course_code for m in config.mappings}
    owner = config.owner or settings.github_owner

    new_mappings: list[RepoMapping] = []
    for c in courses:
        label = settings._sanitise(c.get("course_code", "") or c.get("name", ""))
        if not label or label in existing:
            continue
        mapping = RepoMapping(
            course_code=label,
            canvas_course_id=c.get("id", 0),
            github_repo=label,
            github_owner=owner,
        )
        new_mappings.append(mapping)
        config.mappings.append(mapping)

    if new_mappings:
        save_config(config)
        logger.info("Auto-generated %d new repo mappings", len(new_mappings))

    return new_mappings
