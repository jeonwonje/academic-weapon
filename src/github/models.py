"""Pydantic models for GitHub push configuration and results."""

from __future__ import annotations

from pydantic import BaseModel


class RepoMapping(BaseModel):
    """Maps a Canvas course to a GitHub repo."""

    course_code: str
    canvas_course_id: int
    github_repo: str
    github_owner: str
    branch: str = "main"
    enabled: bool = True
    last_push_at: str | None = None
    last_push_commit: str | None = None


class GitHubConfig(BaseModel):
    """Root config for all GitHub push mappings."""

    owner: str = ""
    commit_prefix: str = "[canvas-sync]"
    mappings: list[RepoMapping] = []


class PushResult(BaseModel):
    """Result of pushing a single course to GitHub."""

    course_code: str
    status: str  # "ok", "skipped", "failed"
    files_changed: int = 0
    commit_sha: str | None = None
    error: str | None = None
