"""Config screen — toggle courses on/off and edit repo names."""

from __future__ import annotations

import json

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from src.config import settings
from src.github.config_manager import load_config, save_config, upsert_mapping
from src.github.models import RepoMapping


class ConfigScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("g", "generate", "Auto-Generate"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(" Configure course → GitHub repo mappings", id="config_header")
        yield VerticalScroll(id="mapping_list")
        yield Horizontal(
            Button("Auto-Generate from Canvas", id="btn_generate", variant="primary"),
            Button("Back", id="btn_back"),
            id="config_actions",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        container = self.query_one("#mapping_list", VerticalScroll)
        container.remove_children()

        config = load_config()
        if not config.mappings:
            container.mount(
                Static(
                    "No mappings yet. Press [bold]Auto-Generate[/bold] to create "
                    "mappings from your Canvas courses, or add them manually."
                )
            )
            return

        for m in config.mappings:
            row = Horizontal(
                Checkbox(m.course_code, value=m.enabled, id=f"chk_{m.course_code}"),
                Label(" → "),
                Input(
                    value=m.github_repo,
                    placeholder="repo name",
                    id=f"repo_{m.course_code}",
                ),
                classes="mapping_row",
            )
            container.mount(row)

        container.mount(
            Static(
                "\n Tick to enable push. Edit the text field to change the GitHub repo name."
            )
        )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if not event.checkbox.id or not event.checkbox.id.startswith("chk_"):
            return
        course_code = event.checkbox.id[4:]
        config = load_config()
        for m in config.mappings:
            if m.course_code == course_code:
                m.enabled = event.value
                save_config(config)
                break

    def on_input_changed(self, event: Input.Changed) -> None:
        if not event.input.id or not event.input.id.startswith("repo_"):
            return
        course_code = event.input.id[5:]
        config = load_config()
        for m in config.mappings:
            if m.course_code == course_code:
                m.github_repo = event.value
                save_config(config)
                break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_generate":
            self.action_generate()
        elif event.button.id == "btn_back":
            self.app.pop_screen()

    def action_generate(self) -> None:
        """Auto-generate mappings from courses.json."""
        courses_path = settings.data_dir / "courses.json"
        if not courses_path.exists():
            self.notify("No courses.json found. Run a Canvas sync first.", severity="error")
            return

        courses = json.loads(courses_path.read_text())
        config = load_config()
        owner = config.owner or settings.github_owner

        if not owner:
            self.notify("Set GITHUB_OWNER in .env or Settings first.", severity="error")
            return

        existing = {m.course_code for m in config.mappings}
        added = 0
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
            upsert_mapping(mapping)
            added += 1

        self.notify(f"Generated {added} new mapping(s).")
        self._refresh_list()
