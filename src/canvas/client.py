"""Async Canvas LMS API client with pagination and rate-limit handling."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, TypeVar, Type

import httpx
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Regex for parsing Link header
_LINK_RE = re.compile(r'<([^>]+)>;\s*rel="(\w+)"')


class CanvasClient:
    """Async client for the Canvas LMS REST API."""

    def __init__(self, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.canvas_base,
            headers=settings.headers,
            timeout=timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "CanvasClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── Core request with pagination + rate-limit handling ──────────────

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Single request with rate-limit retry."""
        max_retries = 5
        for attempt in range(max_retries):
            resp = await self._client.request(method, url, params=params, **kwargs)

            if resp.status_code == 429:
                # Rate limited – back off exponentially
                wait = 2 ** attempt
                remaining = resp.headers.get("X-Rate-Limit-Remaining", "?")
                logger.warning(
                    "Rate limited (remaining=%s). Retrying in %ds…", remaining, wait
                )
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            return resp

        raise RuntimeError("Canvas API rate limit: max retries exceeded")

    async def _get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """GET a single page and return parsed JSON."""
        resp = await self._request("GET", path, params=params)
        return resp.json()

    async def _get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """GET all pages of a paginated endpoint, returns combined list."""
        params = dict(params or {})
        params.setdefault("per_page", 100)

        all_items: list[dict[str, Any]] = []
        url: str | None = path

        while url:
            resp = await self._request("GET", url, params=params)
            data = resp.json()
            if isinstance(data, list):
                all_items.extend(data)
            else:
                # Some endpoints return a dict with a results key
                all_items.append(data)

            # Follow pagination via Link header
            url = self._next_link(resp)
            # After the first request params are embedded in the Link URL
            params = None

        return all_items

    @staticmethod
    def _next_link(resp: httpx.Response) -> str | None:
        """Parse the Link header and return the 'next' URL if present."""
        link_header = resp.headers.get("Link", "")
        for url, rel in _LINK_RE.findall(link_header):
            if rel == "next":
                return url
        return None

    def _parse_list(self, data: list[dict[str, Any]], model: Type[T]) -> list[T]:
        """Parse a list of dicts into pydantic models, skipping bad entries."""
        results: list[T] = []
        for item in data:
            try:
                results.append(model.model_validate(item))
            except Exception as exc:
                logger.debug("Skipping unparseable item: %s", exc)
        return results

    # ── High-level API methods ──────────────────────────────────────────

    async def list_courses(
        self,
        enrollment_state: str = "active",
        include: list[str] | None = None,
    ) -> list:
        """List courses for the authenticated user."""
        from src.canvas.models import Course

        params: dict[str, Any] = {"enrollment_state": enrollment_state}
        if include:
            params["include[]"] = include

        data = await self._get_paginated("/courses", params=params)
        return self._parse_list(data, Course)

    async def list_files(self, course_id: int) -> list:
        """List all files in a course."""
        from src.canvas.models import CanvasFile

        data = await self._get_paginated(f"/courses/{course_id}/files")
        return self._parse_list(data, CanvasFile)

    async def list_folders(self, course_id: int) -> list:
        """List all folders in a course."""
        from src.canvas.models import Folder

        data = await self._get_paginated(f"/courses/{course_id}/folders")
        return self._parse_list(data, Folder)

    async def list_assignments(self, course_id: int) -> list:
        """List all assignments in a course."""
        from src.canvas.models import Assignment

        params: dict[str, Any] = {
            "include[]": ["submission"],
            "order_by": "due_at",
        }
        data = await self._get_paginated(
            f"/courses/{course_id}/assignments", params=params
        )
        return self._parse_list(data, Assignment)

    async def list_modules(self, course_id: int) -> list:
        """List all modules in a course."""
        from src.canvas.models import Module

        params: dict[str, Any] = {"include[]": ["items", "content_details"]}
        data = await self._get_paginated(
            f"/courses/{course_id}/modules", params=params
        )
        return self._parse_list(data, Module)

    async def list_announcements(self, context_codes: list[str]) -> list:
        """List announcements for the given courses.

        context_codes: e.g. ["course_12345", "course_67890"]
        """
        from src.canvas.models import Announcement

        params: dict[str, Any] = {"context_codes[]": context_codes}
        data = await self._get_paginated("/announcements", params=params)
        return self._parse_list(data, Announcement)

    async def list_calendar_events(
        self,
        context_codes: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        event_type: str = "event",
    ) -> list:
        """List calendar events / assignment events."""
        from src.canvas.models import CalendarEvent

        params: dict[str, Any] = {
            "context_codes[]": context_codes,
            "type": event_type,
            "all_events": True,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = await self._get_paginated("/calendar_events", params=params)
        return self._parse_list(data, CalendarEvent)

    async def download_file(self, url: str, dest: str) -> None:
        """Stream-download a file from its Canvas URL to a local path."""
        async with self._client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
