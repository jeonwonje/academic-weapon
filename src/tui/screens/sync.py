"""Sync screen — live view of Canvas sync + GitHub push progress."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog


class SyncScreen(Screen):
    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(highlight=True, markup=True, id="sync_log")
        yield Footer()

    def on_mount(self) -> None:
        self._run_sync()

    def _run_sync(self) -> None:
        log = self.query_one("#sync_log", RichLog)
        log.write("[bold]Starting Canvas sync + GitHub push…[/bold]\n")
        self.run_worker(self._do_sync, exclusive=True)

    async def _do_sync(self) -> None:
        log = self.query_one("#sync_log", RichLog)

        handler = _RichLogHandler(log)
        handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(handler)

        try:
            from src.github.orchestrator import sync_and_push

            result = await sync_and_push()

            log.write("\n[bold green]--- Sync Complete ---[/bold green]")
            for s in result.sync_summaries:
                course = s.get("course", "?")
                files = s.get("files", {})
                if isinstance(files, dict) and "error" not in files:
                    dl = len(files.get("downloaded", []))
                    log.write(f"  {course}: {dl} new files")
                else:
                    log.write(f"  {course}: {files}")

            if result.push_results:
                log.write("\n[bold blue]--- GitHub Push ---[/bold blue]")
                for r in result.push_results:
                    if r.status == "ok":
                        log.write(f"  [green]OK[/green] {r.course_code}: {r.files_changed} files pushed")
                    elif r.status == "skipped":
                        log.write(f"  [dim]SKIP[/dim] {r.course_code}: no changes")
                    else:
                        log.write(f"  [red]FAIL[/red] {r.course_code}: {r.error}")

            log.write("\n[bold]Done. Press Escape to go back.[/bold]")
        except Exception as exc:
            log.write(f"\n[bold red]Error: {exc}[/bold red]")
        finally:
            root.removeHandler(handler)

    def action_go_back(self) -> None:
        self.app.pop_screen()


class PushScreen(Screen):
    """Push-only screen — pushes to GitHub without re-syncing Canvas."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(highlight=True, markup=True, id="push_log")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#push_log", RichLog)
        log.write("[bold]Pushing to GitHub…[/bold]\n")
        self.run_worker(self._do_push, exclusive=True)

    async def _do_push(self) -> None:
        import logging

        log = self.query_one("#push_log", RichLog)
        handler = _RichLogHandler(log)
        handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(handler)

        try:
            from src.github.pusher import push_all

            results = await push_all()

            if not results:
                log.write("[yellow]No enabled mappings found. Configure repos first.[/yellow]")
            else:
                log.write("\n[bold blue]--- Results ---[/bold blue]")
                for r in results:
                    if r.status == "ok":
                        log.write(f"  [green]OK[/green] {r.course_code}: {r.files_changed} files")
                    elif r.status == "skipped":
                        log.write(f"  [dim]SKIP[/dim] {r.course_code}: no changes")
                    else:
                        log.write(f"  [red]FAIL[/red] {r.course_code}: {r.error}")

            log.write("\n[bold]Done. Press Escape to go back.[/bold]")
        except Exception as exc:
            log.write(f"\n[bold red]Error: {exc}[/bold red]")
        finally:
            root.removeHandler(handler)

    def action_go_back(self) -> None:
        self.app.pop_screen()


class _RichLogHandler(logging.Handler):
    """Logging handler that writes to a Textual RichLog widget."""

    def __init__(self, rich_log: RichLog) -> None:
        super().__init__()
        self._log = rich_log

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._log.write(msg)
        except Exception:
            pass
