"""Canvas Auto Updater TUI — Textual application."""

from __future__ import annotations

from textual.app import App

from src.tui.screens.config import ConfigScreen
from src.tui.screens.dashboard import DashboardScreen
from src.tui.screens.settings import SettingsScreen
from src.tui.screens.sync import PushScreen, SyncScreen

CSS = """
Screen {
    background: $surface;
}

#status_bar {
    height: 1;
    background: $accent;
    color: $text;
    padding: 0 1;
}

#config_header, #settings_header {
    height: 1;
    background: $accent;
    color: $text;
    padding: 0 1;
}

#mapping_list {
    height: 1fr;
    padding: 1;
}

.mapping_row {
    height: auto;
    padding: 0 1;
}

.mapping_row Checkbox {
    width: 24;
}

.mapping_row Label {
    width: 3;
    padding: 1 0;
}

.mapping_row Input {
    width: 1fr;
}

#config_actions {
    height: auto;
    padding: 1;
}

#config_actions Button {
    margin: 0 1;
}

VerticalScroll Label {
    padding: 1 1 0 1;
}

VerticalScroll Input {
    margin: 0 1;
}

VerticalScroll Button {
    margin: 1;
}
"""


class CanvasTUI(App):
    """Canvas Auto Updater — sync from Canvas, push to GitHub."""

    TITLE = "Canvas Auto Updater"
    CSS = CSS
    SCREENS = {
        "dashboard": DashboardScreen,
        "config": ConfigScreen,
        "settings": SettingsScreen,
        "sync": SyncScreen,
        "push": PushScreen,
    }

    def on_mount(self) -> None:
        self.push_screen("dashboard")


def main() -> None:
    app = CanvasTUI()
    app.run()


if __name__ == "__main__":
    main()
