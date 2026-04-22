"""Stats screen for NBA league leaders."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from tipoff.api import NBAClient

STAT_CATEGORIES = {
    "PTS": "Points",
    "AST": "Assists",
    "REB": "Rebounds",
    "STL": "Steals",
    "BLK": "Blocks",
}


class StatsScreen(Screen):
    """Screen for viewing NBA stats leaders."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("1", "show_points", "Points"),
        Binding("2", "show_assists", "Assists"),
        Binding("3", "show_rebounds", "Rebounds"),
        Binding("4", "show_steals", "Steals"),
        Binding("5", "show_blocks", "Blocks"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    StatsScreen {
        background: $surface;
    }

    StatsScreen .stats-title {
        width: 100%;
        height: 3;
        align: center middle;
        text-style: bold;
        background: $primary;
        color: $text;
    }

    StatsScreen .stats-scroll {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    StatsScreen .tab-hint {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
    }

    StatsScreen .loading {
        width: 100%;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self._current_category = "PTS"
        self._leaders_data: dict = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("NBA Stats Leaders", classes="stats-title", id="stats-title")
        yield Static("1: Points | 2: Assists | 3: Rebounds | 4: Steals | 5: Blocks | r: Refresh", classes="tab-hint")
        with VerticalScroll(classes="stats-scroll", id="stats-scroll"):
            yield Label("Loading stats...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load stats data."""
        self.run_worker(self._fetch_stats())

    async def _fetch_stats(self) -> None:
        """Fetch stats leaders for the current category."""
        try:
            from tipoff.api import nba_stats

            self._leaders_data = await nba_stats.get_stats_leaders(self._current_category)
            self._render_stats()
        except Exception as e:
            self.notify(f"Error loading stats: {e}", severity="error")

    def _render_stats(self) -> None:
        """Render the stats leaders table."""
        scroll = self.query_one("#stats-scroll", VerticalScroll)
        scroll.remove_children()

        category_name = STAT_CATEGORIES.get(self._current_category, self._current_category)

        # Update title
        title = self.query_one("#stats-title", Static)
        title.update(f"NBA {category_name} Leaders")

        if not self._leaders_data:
            scroll.mount(Label(f"No {category_name} data available", classes="loading"))
            return

        table = DataTable(id="stats-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("#", "Player", "Team", category_name)

        for leader in self._leaders_data:
            table.add_row(
                str(leader.rank),
                leader.player_name,
                leader.team_abbreviation,
                leader.value,
            )

        scroll.mount(table)

    def _switch_category(self, category: str) -> None:
        """Switch to a different stats category."""
        self._current_category = category
        self.run_worker(self._fetch_stats())

    def action_show_points(self) -> None:
        self._switch_category("PTS")

    def action_show_assists(self) -> None:
        self._switch_category("AST")

    def action_show_rebounds(self) -> None:
        self._switch_category("REB")

    def action_show_steals(self) -> None:
        self._switch_category("STL")

    def action_show_blocks(self) -> None:
        self._switch_category("BLK")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        from tipoff.api import nba_stats

        nba_stats.clear_cache()
        self.run_worker(self._fetch_stats())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        self.app.exit()
