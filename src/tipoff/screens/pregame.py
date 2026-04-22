"""Pre-game screen for NBA matchup previews."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static

from tipoff.api import NBAClient
from tipoff.api.models import NBAGame


class PreGameScreen(Screen):
    """Screen showing pre-game matchup information."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    PreGameScreen {
        background: $surface;
    }

    PreGameScreen .pregame-header {
        width: 100%;
        height: auto;
        padding: 1 2;
        border-bottom: solid $primary;
    }

    PreGameScreen .matchup-row {
        width: 100%;
        height: auto;
        align: center middle;
    }

    PreGameScreen .team-panel {
        width: 1fr;
        height: auto;
        padding: 1;
        border: solid $primary;
    }

    PreGameScreen .team-name {
        text-style: bold;
        width: 100%;
        height: 1;
    }

    PreGameScreen .team-record {
        color: $text-muted;
        width: 100%;
        height: 1;
    }

    PreGameScreen .vs-label {
        width: auto;
        text-align: center;
        padding: 0 1;
        color: $accent;
        text-style: bold;
    }

    PreGameScreen .game-info {
        width: 100%;
        height: auto;
        padding: 1 2;
        text-align: center;
    }

    PreGameScreen .section-title {
        width: 100%;
        height: 1;
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin-top: 1;
        margin-bottom: 1;
    }

    PreGameScreen .stat-row {
        width: 100%;
        height: 1;
    }

    PreGameScreen .stat-label {
        width: 12;
        color: $text-muted;
    }

    PreGameScreen .stat-away {
        width: 1fr;
        text-align: right;
    }

    PreGameScreen .stat-home {
        width: 1fr;
    }

    PreGameScreen .series-info {
        width: 100%;
        height: auto;
        text-align: center;
        color: $accent;
        text-style: bold;
    }

    PreGameScreen .loading {
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
        with Vertical(classes="pregame-header", id="pregame-header"):
            yield Label("Loading...", id="matchup-title")
        with VerticalScroll(id="pregame-content"):
            yield Label("Loading matchup info...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load pre-game data."""
        self.run_worker(self._fetch_pregame())

    async def _fetch_pregame(self) -> None:
        """Fetch pre-game information."""
        try:
            summary = await self.client.get_game_summary(self.game.id)
            self._render_pregame(summary)
        except Exception:
            # Fall back to basic info from game data
            self._render_basic_pregame()

    def _render_pregame(self, summary: dict) -> None:
        """Render pre-game matchup from ESPN summary data."""
        self._render_basic_pregame()

        content = self.query_one("#pregame-content", VerticalScroll)
        content.remove_children()

        # Broadcast info
        broadcasts = self.game.broadcasts
        if broadcasts:
            content.mount(Static(f"TV: {', '.join(broadcasts)}", classes="game-info"))

        # Series info
        if self.game.series and self.game.series.summary:
            content.mount(Static(self.game.series.summary, classes="series-info"))

    def _render_basic_pregame(self) -> None:
        """Render basic pre-game info from game data alone."""
        away = self.game.away_team
        home = self.game.home_team

        # Update title
        title = self.query_one("#matchup-title", Label)
        title.update(f"{away.abbreviation} @ {home.abbreviation}")

        content = self.query_one("#pregame-content", VerticalScroll)
        content.remove_children()

        # Game time and venue
        from tipoff.widgets.game_card import get_local_time_with_tz

        game_time = get_local_time_with_tz(self.game.date)
        if game_time:
            content.mount(Static(f"Tip-off: {game_time}", classes="game-info"))
        if self.game.venue:
            content.mount(Static(f"Venue: {self.game.venue}", classes="game-info"))

        # Team panels
        content.mount(Static("── Matchup ──", classes="section-title"))
        with Horizontal(classes="matchup-row"):
            with Vertical(classes="team-panel"):
                content.mount(Label(away.name or away.abbreviation, classes="team-name"))
                record = f"{away.wins}-{away.losses}" if away.wins or away.losses else ""
                if record:
                    content.mount(Label(record, classes="team-record"))
            with Vertical(classes="team-panel"):
                content.mount(Label(home.name or home.abbreviation, classes="team-name"))
                record = f"{home.wins}-{home.losses}" if home.wins or home.losses else ""
                if record:
                    content.mount(Label(record, classes="team-record"))

        # Series info
        if self.game.series and self.game.series.summary:
            content.mount(Static("── Series ──", classes="section-title"))
            content.mount(Static(self.game.series.summary, classes="series-info"))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.client.clear_cache()
        self.run_worker(self._fetch_pregame())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        self.app.exit()
