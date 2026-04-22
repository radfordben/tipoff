"""Series detail screen for playoff matchup details."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from tipoff.api import NBAClient
from tipoff.api.models import NBASeries, format_period_short


class SeriesDetailScreen(Screen):
    """Screen showing detailed series information."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    SeriesDetailScreen {
        background: $surface;
    }

    SeriesDetailScreen .series-header {
        width: 100%;
        height: auto;
        padding: 1 2;
        border-bottom: solid $primary;
    }

    SeriesDetailScreen .series-teams {
        width: 100%;
        height: auto;
        align: center middle;
    }

    SeriesDetailScreen .series-status {
        width: 100%;
        height: 1;
        text-align: center;
        color: $accent;
        text-style: bold;
    }

    SeriesDetailScreen .section-title {
        width: 100%;
        height: 1;
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin-top: 1;
        margin-bottom: 1;
    }

    SeriesDetailScreen .no-games {
        width: 100%;
        padding: 1;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, series: NBASeries, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.series = series

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="series-header", id="series-header"):
            yield Static(self._format_series_header(), id="series-teams")
            yield Static(self.series.summary or "", classes="series-status", id="series-status")
        with VerticalScroll(id="series-content"):
            yield Label("Loading series details...", id="series-detail")
        yield Footer()

    def on_mount(self) -> None:
        """Load series game data."""
        self.run_worker(self._fetch_series_data())

    def _format_series_header(self) -> str:
        """Format the series header text."""
        higher = self.series.higher_seed
        lower = self.series.lower_seed
        seed_h = f"({higher.seed})" if higher.seed else ""
        seed_l = f"({lower.seed})" if lower.seed else ""
        return f"{seed_h} {higher.abbreviation} vs {seed_l} {lower.abbreviation}"

    async def _fetch_series_data(self) -> None:
        """Fetch game-by-game results for the series."""
        try:
            # Try to get games from the scoreboard that belong to this series
            games = await self.client.get_scoreboard()
            series_games = [g for g in games if g.series and g.series.id == self.series.id]
            self._render_games(series_games)
        except Exception as e:
            self.notify(f"Error loading series: {e}", severity="error")

    def _render_games(self, games: list) -> None:
        """Render the series games table."""
        content = self.query_one("#series-content", VerticalScroll)
        content.remove_children()

        if not games:
            content.mount(Label("No games data available for this series", classes="no-games"))
            return

        # Section title
        content.mount(Static("Game Results", classes="section-title"))

        # Game results table
        table = DataTable(id="games-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Game", "Date", "Away", "Score", "Home", "Score", "Status")

        for i, game in enumerate(sorted(games, key=lambda g: g.date), 1):
            away_score = str(game.away_score) if game.status != "FUT" else "-"
            home_score = str(game.home_score) if game.status != "FUT" else "-"
            status = format_period_short(game.period) if game.status == "LIVE" else game.status
            if game.status == "FINAL" and game.period > 4:
                status = f"F/{format_period_short(game.period)}"
            table.add_row(
                str(i),
                game.date[:10] if game.date else "-",
                game.away_team.abbreviation,
                away_score,
                game.home_team.abbreviation,
                home_score,
                status,
            )

        content.mount(table)

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Manually refresh the series."""
        self.client.clear_cache()
        self.run_worker(self._fetch_series_data())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
