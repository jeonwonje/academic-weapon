"""Pydantic models for Canvas LMS API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Course ──────────────────────────────────────────────────────────────────

class Course(BaseModel):
    id: int
    name: str = ""
    course_code: str = ""
    workflow_state: str = ""
    start_at: datetime | None = None
    end_at: datetime | None = None
    time_zone: str | None = None
    syllabus_body: str | None = None
    enrollments: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def label(self) -> str:
        """Human-readable short label, e.g. 'CS2103T'."""
        return self.course_code or self.name


# ── Folder ──────────────────────────────────────────────────────────────────

class Folder(BaseModel):
    id: int
    name: str = ""
    full_name: str = ""
    parent_folder_id: int | None = None
    files_url: str | None = None
    folders_url: str | None = None
    position: int | None = None
    files_count: int = 0
    folders_count: int = 0


# ── File ────────────────────────────────────────────────────────────────────

class CanvasFile(BaseModel):
    id: int
    folder_id: int | None = None
    display_name: str = ""
    filename: str = ""
    content_type: str = Field(default="", alias="content-type")
    url: str = ""
    size: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    locked: bool = False
    hidden: bool = False

    model_config = {"populate_by_name": True}


# ── Assignment ──────────────────────────────────────────────────────────────

class Assignment(BaseModel):
    id: int
    name: str = ""
    description: str | None = None
    due_at: datetime | None = None
    lock_at: datetime | None = None
    unlock_at: datetime | None = None
    points_possible: float | None = None
    submission_types: list[str] = Field(default_factory=list)
    course_id: int | None = None
    html_url: str = ""
    published: bool = True
    has_submitted_submissions: bool = False

    @property
    def is_upcoming(self) -> bool:
        if self.due_at is None:
            return True  # undated counts as upcoming
        return self.due_at > datetime.utcnow()


# ── Announcement ────────────────────────────────────────────────────────────

class Announcement(BaseModel):
    id: int
    title: str = ""
    message: str = ""
    posted_at: datetime | None = None
    delayed_post_at: datetime | None = None
    context_code: str = ""
    author: dict[str, Any] | None = None


# ── Calendar Event ──────────────────────────────────────────────────────────

class CalendarEvent(BaseModel):
    id: int | str  # can be synthetic like "assignment_987"
    title: str = ""
    start_at: datetime | None = None
    end_at: datetime | None = None
    description: str | None = None
    location_name: str | None = None
    context_code: str = ""
    all_day: bool = False
    workflow_state: str = ""
    assignment: dict[str, Any] | None = None


# ── Module ──────────────────────────────────────────────────────────────────

class Module(BaseModel):
    id: int
    name: str = ""
    position: int | None = None
    unlock_at: datetime | None = None
    items_count: int = 0
    items_url: str | None = None
    state: str | None = None
    published: bool | None = None
    items: list[ModuleItem] = Field(default_factory=list)


class ModuleItem(BaseModel):
    id: int
    module_id: int | None = None
    title: str = ""
    type: str = ""  # File, Page, Assignment, Quiz, etc.
    content_id: int | None = None
    html_url: str | None = None
    url: str | None = None
    position: int | None = None


# ── Sync metadata (local tracking) ─────────────────────────────────────────

class FileSyncRecord(BaseModel):
    """Tracks local sync state for a single Canvas file."""
    file_id: int
    display_name: str = ""
    updated_at: str = ""
    size: int = 0
    local_path: str = ""
    content_type: str = ""
