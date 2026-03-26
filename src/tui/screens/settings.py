"""Settings screen — edit global GitHub push settings."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from src.github.config_manager import load_config, save_config


class SettingsScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(" Global GitHub Settings", id="settings_header")
        yield VerticalScroll(
            Label("GitHub Owner (username):"),
            Input(id="input_owner", placeholder="e.g. jeonwonje"),
            Label("Commit Prefix:"),
            Input(id="input_prefix", placeholder="e.g. [canvas-sync]"),
            Button("Save", id="btn_save", variant="primary"),
            Button("Back", id="btn_back"),
        )
        yield Footer()

    def on_mount(self) -> None:
        config = load_config()
        self.query_one("#input_owner", Input).value = config.owner
        self.query_one("#input_prefix", Input).value = config.commit_prefix

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            config = load_config()
            config.owner = self.query_one("#input_owner", Input).value
            config.commit_prefix = self.query_one("#input_prefix", Input).value
            # Update owner on all mappings that use the old default
            for m in config.mappings:
                if m.github_owner != config.owner:
                    m.github_owner = config.owner
            save_config(config)
            self.notify("Settings saved.")
        elif event.button.id == "btn_back":
            self.app.pop_screen()
