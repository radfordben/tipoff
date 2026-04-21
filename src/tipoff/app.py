"""Main Tipoff application."""

from __future__ import annotations

from textual.app import App
from textual.theme import Theme

from tipoff.api import NBAClient


class TipoffApp(App[None]):
    """NBA Playoff Tracker TUI."""

    TITLE = "Tipoff"
    SUB_TITLE = "NBA Playoff Tracker"

    CSS = """
    Screen {
        background: $surface;
    }
    """

    def __init__(self, refresh_interval: int = 30) -> None:
        super().__init__()
        self.refresh_interval = refresh_interval
        self.client = NBAClient()

    def on_mount(self) -> None:
        from tipoff.screens.schedule import ScheduleScreen

        self.register_theme(
            Theme(
                name="nba",
                primary="#1D428A",
                secondary="#C8102E",
                background="#0d1117",
                surface="#161b22",
                foreground="#e6edf3",
                success="#38b000",
                warning="#ffc107",
                error="#ff6b6b",
                accent="#ffd700",
                dark=True,
            )
        )
        self.theme = "nba"
        self.push_screen(ScheduleScreen(client=self.client, refresh_interval=self.refresh_interval))

    async def on_unmount(self) -> None:
        await self.client.aclose()
