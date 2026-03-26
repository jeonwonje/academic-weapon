"""Dashboard screen — overview of all courses and their GitHub push status."""

from __future__ import annotations

from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static


def _time_ago(iso: str | None) -> str:
    if not iso:
        return "Never"
    try:
        dt = datetime.fromisoformat(iso)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return iso[:10] if iso else "?"


class DashboardScreen(Screen):
    BINDINGS = [
        ("s", "sync_all", "Sync All"),
        ("p", "push_all", "Push All"),
        ("c", "app.push_screen('config')", "Config"),
        ("t", "app.push_screen('settings')", "Settings"),
        ("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading…", id="status_bar")
        yield DataTable(id="course_table")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        from src.github.config_manager import load_config

        table = self.query_one("#course_table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Course", "GitHub Repo", "Last Push", "Status")

        config = load_config()
        if not config.mappings:
            self.query_one("#status_bar", Static).update(
                "No GitHub mappings configured. Press [bold]c[/bold] to configure."
            )
            return

        enabled = sum(1 for m in config.mappings if m.enabled)
        self.query_one("#status_bar", Static).update(
            f" {len(config.mappings)} courses configured, {enabled} enabled"
        )

        for m in config.mappings:
            if m.enabled:
                status = "OK" if m.last_push_at else "Not pushed"
            else:
                status = "Disabled"
            repo = f"{m.github_owner}/{m.github_repo}" if m.enabled else "(disabled)"
            table.add_row(
                m.course_code,
                repo,
                _time_ago(m.last_push_at),
                status,
                key=m.course_code,
            )

    async def action_sync_all(self) -> None:
        await self.app.push_screen("sync")

    async def action_push_all(self) -> None:
        self.app.push_screen("push")
