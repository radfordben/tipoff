"""Box score screen for viewing player-level game stats."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from tipoff.api import NBAClient
from tipoff.api.models import NBAGame

# Column sets for responsive display
FULL_COLUMNS = ["Player", "MIN", "FG", "FGA", "3P", "3PA", "FT", "FTA", "REB", "AST", "STL", "BLK", "TO", "PF", "PTS"]
COMPACT_COLUMNS = ["Player", "PTS", "REB", "AST"]
WIDE_MIN_WIDTH = 100


class BoxScoreScreen(Screen):
    """Screen showing full player box scores for a game."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    BoxScoreScreen {
        background: $surface;
    }

    BoxScoreScreen .box-header {
        width: 100%;
        height: auto;
        padding: 1 2;
        border-bottom: solid $primary;
    }

    BoxScoreScreen .team-section {
        width: 100%;
        height: auto;
        margin-bottom: 2;
    }

    BoxScoreScreen .team-label {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    BoxScoreScreen .loading {
        width: 100%;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, game: NBAGame, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.game = game

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="box-header", id="box-header"):
            yield Static(f"{self.game.away_team.abbreviation} @ {self.game.home_team.abbreviation}", id="box-title")
        with VerticalScroll(id="box-content"):
            yield Label("Loading box score...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load box score data."""
        self.run_worker(self._fetch_box_score())

    async def _fetch_box_score(self) -> None:
        """Fetch box score data."""
        try:
            from tipoff.api import nba_stats

            box_score = await nba_stats.get_box_score(self.game.id)
            self._render_box_score(box_score)
        except Exception as e:
            self.notify(f"Error loading box score: {e}", severity="error")

    def _render_box_score(self, box_score: dict) -> None:
        """Render box score tables for both teams."""
        content = self.query_one("#box-content", VerticalScroll)
        content.remove_children()

        width = self.size.width
        columns = FULL_COLUMNS if width >= WIDE_MIN_WIDTH else COMPACT_COLUMNS

        for team_key, team_label in [("away", self.game.away_team.name,), ("home", self.game.home_team.name)]:
            team_section = Vertical(classes="team-section")
            team_section.mount(Static(team_label, classes="team-label"))

            table = DataTable()
            table.cursor_type = "row"
            table.zebra_stripes = True

            for col in columns:
                table.add_column(col)

            players = box_score.get(team_key, [])
            for player in players:
                if columns == FULL_COLUMNS:
                    row = [
                        player.player_name,
                        player.minutes,
                        str(player.field_goals_made),
                        str(player.field_goals_attempted),
                        str(player.three_pointers_made),
                        str(player.three_pointers_attempted),
                        str(player.free_throws_made),
                        str(player.free_throws_attempted),
                        str(player.rebounds),
                        str(player.assists),
                        str(player.steals),
                        str(player.blocks),
                        str(player.turnovers),
                        str(player.personal_fouls),
                        str(player.points),
                    ]
                else:
                    row = [
                        player.player_name,
                        str(player.points),
                        str(player.rebounds),
                        str(player.assists),
                    ]
                table.add_row(*row)

            team_section.mount(table)
            content.mount(team_section)

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Manually refresh the box score."""
        self.client.clear_cache()
        self.run_worker(self._fetch_box_score())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
