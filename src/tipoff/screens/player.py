"""Player screen for viewing NBA player profiles."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from tipoff.api import NBAClient


class PlayerScreen(Screen):
    """Screen for viewing an NBA player's profile and stats."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    PlayerScreen {
        background: $surface;
    }

    PlayerScreen .player-header {
        width: 100%;
        height: auto;
        padding: 1 2;
        border-bottom: solid $primary;
    }

    PlayerScreen .player-name {
        text-style: bold;
        width: 100%;
        height: 1;
    }

    PlayerScreen .player-info {
        width: 100%;
        height: auto;
        color: $text-muted;
    }

    PlayerScreen .info-row {
        width: 100%;
        height: 1;
    }

    PlayerScreen .info-label {
        width: 12;
        color: $text-muted;
    }

    PlayerScreen .info-value {
        width: 1fr;
    }

    PlayerScreen .section-title {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $primary;
        margin-top: 1;
        margin-bottom: 1;
    }

    PlayerScreen .loading {
        width: 100%;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, player_id: str, player_name: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.player_id = player_id
        self.player_name = player_name

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="player-header", id="player-header"):
            yield Label(self.player_name or "Player", classes="player-name", id="player-name")
            yield Label("Loading...", classes="player-info", id="player-info")
        with VerticalScroll(id="player-content"):
            yield Label("Loading...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load player data."""
        self.run_worker(self._fetch_player())

    async def _fetch_player(self) -> None:
        """Fetch player info and game log."""
        try:
            from tipoff.api import nba_stats

            info = await nba_stats.get_player_info(self.player_id)
            games = await nba_stats.get_player_game_log(self.player_id)

            self._render_player(info, games)
        except Exception as e:
            self.notify(f"Error loading player: {e}", severity="error")

    def _render_player(self, info: dict, games: list) -> None:
        """Render player profile."""
        # Update header
        name = self.query_one("#player-name", Label)
        name.update(info.get("name", self.player_name))

        # Info section
        info_widget = self.query_one("#player-info", Label)
        info_lines = []
        if info.get("team"):
            info_lines.append(f"Team: {info['team']}")
        if info.get("position"):
            info_lines.append(f"Position: {info['position']}")
        if info.get("number"):
            info_lines.append(f"#{info['number']}")
        if info.get("height"):
            info_lines.append(f"Height: {info['height']}")
        if info.get("weight"):
            info_lines.append(f"Weight: {info['weight']}")
        if info.get("experience"):
            info_lines.append(f"Experience: {info['experience']} yrs")
        info_widget.update(" | ".join(info_lines))

        # Game log
        content = self.query_one("#player-content", VerticalScroll)
        content.remove_children()

        if not games:
            content.mount(Label("No recent game data available", classes="loading"))
            return

        content.mount(Static("── Recent Games ──", classes="section-title"))

        table = DataTable(id="game-log-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Date", "Opp", "MIN", "PTS", "REB", "AST", "STL", "BLK", "FG%", "3P%")

        for game in games[:10]:  # Show last 10 games
            date = game.get("date", "")[:10]
            opp = game.get("opponent", "")
            minutes = game.get("minutes", "")
            pts = str(game.get("points", 0))
            reb = str(game.get("rebounds", 0))
            ast = str(game.get("assists", 0))
            stl = str(game.get("steals", 0))
            blk = str(game.get("blocks", 0))

            fgm = game.get("field_goals_made", 0)
            fga = game.get("field_goals_attempted", 0)
            fg_pct = f"{fgm}/{fga}" if fga > 0 else "-"

            tpm = game.get("three_pointers_made", 0)
            tpa = game.get("three_pointers_attempted", 0)
            tp_pct = f"{tpm}/{tpa}" if tpa > 0 else "-"

            table.add_row(date, opp, minutes, pts, reb, ast, stl, blk, fg_pct, tp_pct)

        content.mount(table)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        from tipoff.api import nba_stats

        nba_stats.clear_cache()
        self.run_worker(self._fetch_player())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        self.app.exit()
