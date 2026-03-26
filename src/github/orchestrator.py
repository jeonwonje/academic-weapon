"""High-level orchestrator — Canvas sync then GitHub push."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.github.models import PushResult

logger = logging.getLogger(__name__)


@dataclass
class SyncPushResult:
    sync_summaries: list[dict[str, Any]] = field(default_factory=list)
    push_results: list[PushResult] = field(default_factory=list)

    @property
    def push_ok(self) -> int:
        return sum(1 for r in self.push_results if r.status == "ok")

    @property
    def push_failed(self) -> int:
        return sum(1 for r in self.push_results if r.status == "failed")

    @property
    def push_skipped(self) -> int:
        return sum(1 for r in self.push_results if r.status == "skipped")


async def sync_and_push() -> SyncPushResult:
    """Run Canvas sync followed by GitHub push for all enabled courses."""
    from src.canvas.sync import run_sync
    from src.github.pusher import push_all

    # Step 1: Canvas sync
    summaries = await run_sync()

    # Step 2: GitHub push
    push_results = await push_all()

    return SyncPushResult(sync_summaries=summaries, push_results=push_results)
