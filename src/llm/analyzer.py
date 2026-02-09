"""LLM-powered analysis engine — reads synced Canvas data, queries OpenAI."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from src.canvas.course_selection import has_selection, load_selected_course_ids, load_course_registry
from src.config import settings
from src.llm.parser import extract_text, chunk_text
from src.llm.prompts import (
    SYSTEM_PROMPT,
    DAILY_DIGEST_PROMPT,
    DEADLINE_TRACKER_PROMPT,
    COURSE_SUMMARY_PROMPT,
    QUERY_PROMPT,
    get_today,
)

logger = logging.getLogger(__name__)

# Context budget: reserve tokens for the response
MAX_CONTEXT_CHARS = 80_000  # ~20k tokens of context


class Analyzer:
    """Analyses synced Canvas data using OpenAI GPT."""

    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    # ── Private helpers ─────────────────────────────────────────────────

    async def _chat(self, user_prompt: str) -> str:
        """Send a chat completion request and return the response text."""
        resp = await self._openai.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return resp.choices[0].message.content or ""

    def _list_course_dirs(self) -> list[Path]:
        """Return course directories under data/, filtered by selection."""
        data = settings.data_dir
        if not data.exists():
            return []

        all_dirs = [d for d in sorted(data.iterdir()) if d.is_dir()]

        # If the user has selected specific modules, filter to only those
        if has_selection():
            selected_ids = load_selected_course_ids()
            registry = load_course_registry()
            # Build a set of sanitised names for selected courses
            selected_names: set[str] = set()
            for c in registry:
                if c.get("id") in selected_ids:
                    code = c.get("course_code", "") or c.get("name", "")
                    selected_names.add(settings._sanitise(code))

            all_dirs = [
                d for d in all_dirs
                if d.name in selected_names
            ]

        return all_dirs

    def _read_json(self, path: Path) -> list[dict[str, Any]]:
        """Safely read a JSON file, returning an empty list on failure."""
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def _build_all_courses_context(self, include_files: bool = False) -> str:
        """Build a context string from all courses' structured data."""
        parts: list[str] = []
        budget = MAX_CONTEXT_CHARS

        for course_dir in self._list_course_dirs():
            course_name = course_dir.name
            section = [f"\n═══ Course: {course_name} ═══\n"]

            # Assignments (always include — most critical)
            assignments = self._read_json(course_dir / "assignments.json")
            if assignments:
                section.append("── Assignments ──")
                for a in assignments:
                    due = a.get("due_at", "No due date")
                    name = a.get("name", "Untitled")
                    pts = a.get("points_possible", "?")
                    desc = (a.get("description") or "")[:200]
                    section.append(f"  • {name} | Due: {due} | Points: {pts}")
                    if desc:
                        section.append(f"    {desc}")

            # Announcements
            announcements = self._read_json(course_dir / "announcements.json")
            if announcements:
                section.append("── Announcements ──")
                for ann in announcements[:10]:  # limit
                    title = ann.get("title", "")
                    posted = ann.get("posted_at", "")
                    msg = (ann.get("message") or "")[:300]
                    section.append(f"  • [{posted}] {title}")
                    if msg:
                        section.append(f"    {msg}")

            # Calendar events
            events = self._read_json(course_dir / "calendar_events.json")
            if events:
                section.append("── Calendar Events ──")
                for ev in events[:20]:
                    title = ev.get("title", "")
                    start = ev.get("start_at", "")
                    section.append(f"  • {title} | Start: {start}")

            # Modules structure
            modules = self._read_json(course_dir / "modules.json")
            if modules:
                section.append("── Modules ──")
                for mod in modules:
                    section.append(f"  • {mod.get('name', '')}")
                    for item in (mod.get("items") or [])[:10]:
                        section.append(f"    - {item.get('title', '')} ({item.get('type', '')})")

            # Optionally include file content snippets
            if include_files:
                files_dir = course_dir / "files"
                if files_dir.exists():
                    section.append("── File Contents (excerpts) ──")
                    for fp in sorted(files_dir.rglob("*")):
                        if fp.is_file():
                            text = extract_text(fp)
                            if text.strip():
                                excerpt = text[:1000]
                                section.append(f"  [{fp.name}]: {excerpt}…")

            course_text = "\n".join(section)
            if len("\n".join(parts)) + len(course_text) > budget:
                break
            parts.append(course_text)

        return "\n".join(parts)

    def _build_course_context(self, course_code: str) -> str:
        """Build a context string for a single course including file contents."""
        course_dir = settings.data_dir / settings._sanitise(course_code)
        if not course_dir.exists():
            # Try fuzzy match
            for d in self._list_course_dirs():
                if course_code.lower() in d.name.lower():
                    course_dir = d
                    break
            else:
                return f"No data found for course: {course_code}"

        parts: list[str] = [f"Course: {course_dir.name}\n"]

        # Structured data
        for fname in ["assignments.json", "announcements.json", "calendar_events.json", "modules.json"]:
            data = self._read_json(course_dir / fname)
            if data:
                parts.append(f"── {fname.replace('.json', '').replace('_', ' ').title()} ──")
                parts.append(json.dumps(data, indent=1, default=str)[:15000])

        # File contents
        files_dir = course_dir / "files"
        if files_dir.exists():
            parts.append("\n── File Contents ──")
            budget = MAX_CONTEXT_CHARS - len("\n".join(parts))
            for fp in sorted(files_dir.rglob("*")):
                if fp.is_file() and budget > 0:
                    text = extract_text(fp)
                    if text.strip():
                        snippet = text[:min(3000, budget)]
                        parts.append(f"\n[{fp.name}]:\n{snippet}")
                        budget -= len(snippet)

        return "\n".join(parts)[:MAX_CONTEXT_CHARS]

    def _build_query_context(self, question: str) -> str:
        """Build context relevant to a user question.

        Searches across all courses for matching content.
        """
        question_lower = question.lower()
        parts: list[str] = []
        budget = MAX_CONTEXT_CHARS

        # Check if question mentions a specific course
        target_course: str | None = None
        for d in self._list_course_dirs():
            if d.name.lower() in question_lower:
                target_course = d.name
                break

        dirs_to_search = (
            [settings.data_dir / target_course]
            if target_course
            else self._list_course_dirs()
        )

        for course_dir in dirs_to_search:
            course_parts = [f"\n═══ {course_dir.name} ═══"]

            # Always include structured data
            for fname in ["assignments.json", "announcements.json", "calendar_events.json", "modules.json"]:
                data = self._read_json(course_dir / fname)
                if data:
                    text = json.dumps(data, indent=1, default=str)[:8000]
                    course_parts.append(f"── {fname} ──\n{text}")

            # Search file contents for relevance
            files_dir = course_dir / "files"
            if files_dir.exists():
                for fp in sorted(files_dir.rglob("*")):
                    if fp.is_file():
                        text = extract_text(fp)
                        if not text.strip():
                            continue
                        # Simple relevance: check if question keywords appear
                        keywords = [w for w in question_lower.split() if len(w) > 3]
                        if any(kw in text.lower() for kw in keywords):
                            snippet = text[:2000]
                            course_parts.append(f"\n[{fp.name}]:\n{snippet}")

            section = "\n".join(course_parts)
            if len("\n".join(parts)) + len(section) > budget:
                break
            parts.append(section)

        return "\n".join(parts)[:MAX_CONTEXT_CHARS]

    # ── Public API ──────────────────────────────────────────────────────

    async def daily_digest(self) -> str:
        """Generate a daily digest of all courses."""
        context = self._build_all_courses_context()
        if not context.strip():
            return "📭 No course data found. Run /sync first to pull data from Canvas."

        prompt = DAILY_DIGEST_PROMPT.format(today=get_today(), context=context)
        return await self._chat(prompt)

    async def deadlines(self) -> str:
        """Generate a sorted list of all upcoming deadlines."""
        context = self._build_all_courses_context()
        if not context.strip():
            return "📭 No course data found. Run /sync first."

        prompt = DEADLINE_TRACKER_PROMPT.format(today=get_today(), context=context)
        return await self._chat(prompt)

    async def course_summary(self, course_code: str) -> str:
        """Generate a summary for a specific course."""
        context = self._build_course_context(course_code)
        if "No data found" in context:
            return f"❌ {context}"

        prompt = COURSE_SUMMARY_PROMPT.format(
            course_code=course_code, context=context
        )
        return await self._chat(prompt)

    async def answer_query(self, question: str) -> str:
        """Answer a free-form question about course content."""
        context = self._build_query_context(question)
        if not context.strip():
            return "📭 No course data to search. Run /sync first."

        prompt = QUERY_PROMPT.format(
            question=question, context=context, today=get_today()
        )
        return await self._chat(prompt)

    def list_courses(self) -> list[str]:
        """Return a list of synced course codes."""
        return [d.name for d in self._list_course_dirs()]

    def list_recent_files(self, course_code: str, limit: int = 15) -> list[dict[str, str]]:
        """Return recently synced files for a course."""
        course_dir = settings.data_dir / settings._sanitise(course_code)
        if not course_dir.exists():
            # Fuzzy match
            for d in self._list_course_dirs():
                if course_code.lower() in d.name.lower():
                    course_dir = d
                    break
            else:
                return []

        meta_path = course_dir / ".sync_meta.json"
        if not meta_path.exists():
            return []

        try:
            meta = json.loads(meta_path.read_text())
            files = sorted(
                meta.values(),
                key=lambda x: x.get("updated_at", ""),
                reverse=True,
            )[:limit]
            return [
                {"name": f.get("display_name", ""), "updated": f.get("updated_at", ""), "type": f.get("content_type", "")}
                for f in files
            ]
        except Exception:
            return []
