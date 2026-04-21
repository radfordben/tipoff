"""Game screen for viewing live or completed NBA game details."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Header, Label, Static

from tipoff.api import NBAClient
from tipoff.api.models import NBAGame, format_period, format_period_short

WIDE_LAYOUT_MIN_WIDTH = 100


class GameScreen(Screen):
    """Screen for viewing NBA game details."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    GameScreen {
        background: $surface;
    }

    GameScreen .score-section {
        width: 100%;
        height: auto;
        padding: 0 2;
        border-bottom: solid $primary;
    }

    GameScreen .score-box {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1;
    }

    GameScreen .team-line {
        width: 100%;
        height: 1;
    }

    GameScreen .team-name {
        width: 1fr;
        text-style: bold;
    }

    GameScreen .team-score {
        width: 4;
        text-align: right;
        text-style: bold;
    }

    GameScreen .team-record {
        width: auto;
        color: $text-muted;
        padding-left: 1;
    }

    GameScreen .winning-score {
        color: $success;
    }

    GameScreen .status-line {
        width: 100%;
        height: 1;
        text-align: center;
        color: $success;
        text-style: bold;
    }

    GameScreen .series-line {
        width: 100%;
        height: 1;
        text-align: center;
        color: $accent;
        text-style: italic;
    }

    GameScreen .section-title {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $primary;
        border-bottom: dashed $primary;
        margin-bottom: 1;
    }

    GameScreen .content-area {
        width: 100%;
        height: 1fr;
    }

    GameScreen .left-panel {
        width: 1fr;
        height: 100%;
    }

    GameScreen .right-panel {
        width: 1fr;
        height: 100%;
    }

    GameScreen .stat-row {
        width: 100%;
        height: 1;
    }

    GameScreen .stat-label {
        width: 12;
        color: $text-muted;
    }

    GameScreen .stat-value {
        width: 1fr;
        text-align: center;
    }

    GameScreen .no-data {
        width: 100%;
        padding: 1;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, game: NBAGame, refresh_interval: int = 30, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.game = game
        self.refresh_interval = refresh_interval
        self._refresh_timer: Timer | None = None
        self._countdown_timer: Timer | None = None
        self._countdown: int = refresh_interval
        self._summary_data: dict = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="score-section", id="score-section"):
            yield Static("Loading...", id="score-box", classes="score-box")
        with Horizontal(classes="content-area", id="content-area"):
            with VerticalScroll(classes="left-panel", id="left-panel"):
                yield Label("Loading...", id="goals-section")
                yield Label("", id="stats-section")
            with VerticalScroll(classes="right-panel", id="right-panel"):
                yield Label("Loading...", id="pbp-section")
        yield Footer()

    def on_mount(self) -> None:
        """Load game data on mount."""
        self.run_worker(self._fetch_data())
        # Auto-refresh for live games
        if self.game.status in ("LIVE", "HALFTIME"):
            self._countdown = self.refresh_interval
            self._refresh_timer = self.set_interval(self.refresh_interval, callback=self._auto_refresh)
            self._countdown_timer = self.set_interval(1, callback=self._update_countdown)
        self._update_subtitle()

    def on_unmount(self) -> None:
        """Clean up timers."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._countdown_timer:
            self._countdown_timer.stop()

    async def _fetch_data(self) -> None:
        """Fetch game summary data from ESPN."""
        try:
            self._summary_data = await self.client.get_game_summary(self.game.id)
            self._render_game()
        except Exception as e:
            self.notify(f"Error loading game: {e}", severity="error")

    def _render_game(self) -> None:
        """Render the game data to the screen."""
        self._render_score_box()
        self._render_content()

    def _render_score_box(self) -> None:
        """Render the score display at the top."""
        away = self.game.away_team
        home = self.game.home_team

        # Determine winner for coloring
        away_winning = self.game.away_score > self.game.home_score
        home_winning = self.game.home_score > self.game.away_score

        # Status text
        status_text = self._get_status_text()

        # Build score box
        lines = []
        lines.append(f"  {away.abbreviation:3}  {self.game.away_score:>3}  {'*' if away_winning and self.game.status == 'FINAL' else ' '}")
        lines.append(f"  {home.abbreviation:3}  {self.game.home_score:>3}  {'*' if home_winning and self.game.status == 'FINAL' else ' '}")
        lines.append(f"  {status_text}")

        # Quarter scores
        if self.game.away_quarter_scores or self.game.home_quarter_scores:
            q_headers = ["  ", "1", "2", "3", "4"]
            away_q = self.game.away_quarter_scores
            home_q = self.game.home_quarter_scores
            max_q = max(len(away_q), len(home_q))
            for i in range(5, max_q + 1):
                ot = i - 4
                q_headers.append("OT" if ot == 1 else f"{ot}OT")
            q_headers.append("T")
            header_line = " ".join(f"{h:>3}" for h in q_headers)
            away_line = f"{away.abbreviation:>3}" + "".join(f"{s:>3}" for s in away_q) + f"{self.game.away_score:>4}"
            home_line = f"{home.abbreviation:>3}" + "".join(f"{s:>3}" for s in home_q) + f"{self.game.home_score:>4}"
            lines.append("")
            lines.append(header_line)
            lines.append(away_line)
            lines.append(home_line)

        # Series info
        if self.game.series and self.game.series.summary:
            lines.append("")
            lines.append(f"  {self.game.series.summary}")

        try:
            score_box = self.query_one("#score-box", Static)
            score_box.update("\n".join(lines))
        except Exception:
            pass

    def _render_content(self) -> None:
        """Render the main content area (left panel: stats, right panel: play-by-play)."""
        width = self.size.width

        # Stats section
        self._render_stats()

        # Play-by-play section
        self._render_pbp()

        # Adjust layout based on width
        try:
            content = self.query_one("#content-area", Horizontal)
            left = self.query_one("#left-panel", VerticalScroll)
            right = self.query_one("#right-panel", VerticalScroll)

            if width >= WIDE_LAYOUT_MIN_WIDTH:
                content.styles.grid_size = 2
                left.styles.display = "block"
                right.styles.display = "block"
                left.styles.width = "1fr"
                right.styles.width = "1fr"
            else:
                content.styles.grid_size = 1
                left.styles.width = "100%"
                right.styles.width = "100%"
        except Exception:
            pass

    def _render_stats(self) -> None:
        """Render the team stats comparison section."""
        stats_widget = self.query_one("#stats-section", Label)
        # Stats come from the ESPN summary or nba_api box score
        # For now, show a placeholder until we have detailed stats
        stats_widget.update("")

    def _render_pbp(self) -> None:
        """Render the play-by-play section."""
        pbp_widget = self.query_one("#pbp-section", Label)
        # Play-by-play will be populated from the summary data
        pbp_widget.update("Play-by-play loading...")

    def _get_status_text(self) -> str:
        """Get the game status text."""
        status = self.game.status

        if status == "FUT":
            from tipoff.widgets.game_card import get_local_time_with_tz

            local_time = get_local_time_with_tz(self.game.date)
            return local_time or "Scheduled"

        if status == "HALFTIME":
            return "Halftime"

        if status == "LIVE":
            period_str = format_period(self.game.period)
            if period_str and self.game.clock:
                return f"{period_str} {self.game.clock}"
            if period_str:
                return period_str
            return "Live"

        if status == "FINAL":
            if self.game.period > 4:
                return f"Final/{format_period_short(self.game.period)}"
            return "Final"

        if status == "PPD":
            return "Postponed"
        if status == "CNCL":
            return "Cancelled"

        return status

    def _update_subtitle(self) -> None:
        """Update the subtitle with refresh countdown."""
        if self.game.status in ("LIVE", "HALFTIME"):
            self.sub_title = f"{self.game.away_team.abbreviation} @ {self.game.home_team.abbreviation} | Refreshing in {self._countdown}s"
        else:
            self.sub_title = f"{self.game.away_team.abbreviation} @ {self.game.home_team.abbreviation}"

    def _update_countdown(self) -> None:
        """Update the countdown timer."""
        self._countdown -= 1
        if self._countdown < 0:
            self._countdown = self.refresh_interval
        self._update_subtitle()

    def _auto_refresh(self) -> None:
        """Auto-refresh for live games."""
        self._countdown = self.refresh_interval
        if self.game.status in ("LIVE", "HALFTIME"):
            self.client.clear_cache()
            self.run_worker(self._refresh_game())

    async def _refresh_game(self) -> None:
        """Refresh game data."""
        try:
            games = await self.client.get_scoreboard()
            for g in games:
                if g.id == self.game.id:
                    self.game = g
                    self._summary_data = await self.client.get_game_summary(self.game.id)
                    self._render_game()
                    break
        except Exception:
            pass

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Manually refresh the game."""
        self._countdown = self.refresh_interval
        self._update_subtitle()
        self.client.clear_cache()
        self.run_worker(self._fetch_data())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
