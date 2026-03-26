"""Core git operations — init, commit, and push course files to GitHub."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.github.config_manager import load_config, save_config
from src.github.models import GitHubConfig, PushResult, RepoMapping

logger = logging.getLogger(__name__)

GITIGNORE_CONTENTS = """\
# Canvas sync internal metadata
.sync_meta.json
"""

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB — GitHub's hard limit


async def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr).

    Uses create_subprocess_exec (no shell) to avoid injection risks.
    All arguments are passed as a list, never interpolated into a shell string.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


async def _repo_exists(owner: str, repo: str) -> bool:
    """Check if a GitHub repo exists using gh CLI."""
    rc, _, _ = await _run(["gh", "repo", "view", f"{owner}/{repo}"], cwd=Path.cwd())
    return rc == 0


async def _check_large_files(course_dir: Path) -> list[str]:
    """Find files exceeding GitHub's 100MB limit and add them to .gitignore."""
    large: list[str] = []
    gitignore_path = course_dir / ".gitignore"
    existing_ignores = gitignore_path.read_text() if gitignore_path.exists() else ""

    for f in course_dir.rglob("*"):
        if not f.is_file() or ".git" in f.parts:
            continue
        try:
            if f.stat().st_size > MAX_FILE_SIZE:
                rel = f.relative_to(course_dir).as_posix()
                large.append(rel)
                if rel not in existing_ignores:
                    with open(gitignore_path, "a") as fh:
                        fh.write(f"\n# Too large for GitHub (>100MB)\n{rel}\n")
                    logger.warning("File >100MB, added to .gitignore: %s", rel)
        except OSError:
            continue
    return large


async def push_course(mapping: RepoMapping, config: GitHubConfig) -> PushResult:
    """Push a single course directory to its GitHub repo."""
    course_dir = settings.data_dir / mapping.course_code
    if not course_dir.is_dir():
        return PushResult(
            course_code=mapping.course_code,
            status="failed",
            error=f"Course directory not found: {course_dir}",
        )

    prefix = config.commit_prefix

    # 1. Verify remote repo exists
    if not await _repo_exists(mapping.github_owner, mapping.github_repo):
        return PushResult(
            course_code=mapping.course_code,
            status="failed",
            error=f"Repo {mapping.github_owner}/{mapping.github_repo} not found. Create it first: gh repo create {mapping.github_repo} --private",
        )

    # 2. Ensure .gitignore
    gitignore = course_dir / ".gitignore"
    if not gitignore.exists() or ".sync_meta.json" not in gitignore.read_text():
        gitignore.write_text(GITIGNORE_CONTENTS)

    # 3. Check for oversized files
    await _check_large_files(course_dir)

    # 4. Git init if needed
    git_dir = course_dir / ".git"
    if not git_dir.is_dir():
        await _run(["git", "init", "-b", mapping.branch], cwd=course_dir)
        await _run(
            ["git", "remote", "add", "origin",
             f"git@github.com:{mapping.github_owner}/{mapping.github_repo}.git"],
            cwd=course_dir,
        )
        logger.info("Initialized git repo in %s", course_dir)
    else:
        # Ensure remote URL is up to date
        expected = f"git@github.com:{mapping.github_owner}/{mapping.github_repo}.git"
        rc, current_url, _ = await _run(
            ["git", "remote", "get-url", "origin"], cwd=course_dir
        )
        if rc != 0 or current_url != expected:
            await _run(["git", "remote", "remove", "origin"], cwd=course_dir)
            await _run(["git", "remote", "add", "origin", expected], cwd=course_dir)

    # 5. Stage all changes
    await _run(["git", "add", "-A"], cwd=course_dir)

    # 6. Check for changes
    rc, status_out, _ = await _run(["git", "status", "--porcelain"], cwd=course_dir)
    if not status_out:
        return PushResult(
            course_code=mapping.course_code,
            status="skipped",
        )

    files_changed = len(status_out.strip().splitlines())

    # 7. Commit
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = f"{prefix} Update {mapping.course_code}: {files_changed} files changed ({now})"
    rc, _, stderr = await _run(["git", "commit", "-m", msg], cwd=course_dir)
    if rc != 0:
        return PushResult(
            course_code=mapping.course_code,
            status="failed",
            error=f"git commit failed: {stderr}",
        )

    # Get commit SHA
    _, sha, _ = await _run(["git", "rev-parse", "HEAD"], cwd=course_dir)

    # 8. Push
    rc, _, stderr = await _run(
        ["git", "push", "-u", "origin", mapping.branch], cwd=course_dir
    )
    if rc != 0:
        return PushResult(
            course_code=mapping.course_code,
            status="failed",
            files_changed=files_changed,
            commit_sha=sha,
            error=f"git push failed: {stderr}",
        )

    logger.info("Pushed %s: %d files changed (%s)", mapping.course_code, files_changed, sha[:7])
    return PushResult(
        course_code=mapping.course_code,
        status="ok",
        files_changed=files_changed,
        commit_sha=sha,
    )


async def push_all() -> list[PushResult]:
    """Push all enabled course mappings to GitHub."""
    config = load_config()
    results: list[PushResult] = []

    enabled = [m for m in config.mappings if m.enabled]
    if not enabled:
        logger.info("No enabled GitHub mappings — nothing to push.")
        return results

    for mapping in enabled:
        result = await push_course(mapping, config)
        results.append(result)

        # Update last push metadata on success
        if result.status == "ok":
            mapping.last_push_at = datetime.now(timezone.utc).isoformat()
            mapping.last_push_commit = result.commit_sha
            save_config(config)

    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    logger.info("Push complete: %d ok, %d skipped, %d failed", ok, skipped, failed)

    return results
