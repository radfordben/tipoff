"""Game screen for viewing live or completed NBA game details."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
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
        padding: 1 2;
        border-bottom: wide $primary;
        background: $surface-darken-1;
    }

    GameScreen .score-box {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 0 1;
    }

    GameScreen .section-title {
        width: 100%;
        height: 1;
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin-top: 1;
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
        text-style: italic;
    }

    GameScreen .quarter-table {
        width: 100%;
        height: auto;
        padding: 1 0;
    }

    GameScreen .series-banner {
        width: 100%;
        height: 1;
        text-align: center;
        color: $accent;
        text-style: bold;
        background: $surface-lighten-1;
        padding: 0 1;
    }

    GameScreen .venue-info {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
        text-style: italic;
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
                yield Label("", id="stats-section")
            with VerticalScroll(classes="right-panel", id="right-panel"):
                yield Label("", id="pbp-section")
        yield Footer()

    def on_mount(self) -> None:
        """Load game data on mount."""
        self.run_worker(self._fetch_data())
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
        """Render the score display at the top using Rich text for alignment."""
        away = self.game.away_team
        home = self.game.home_team
        away_winning = self.game.away_score > self.game.home_score
        home_winning = self.game.home_score > self.game.away_score
        status_text = self._get_status_text()

        # Build a Rich Text object for beautiful score display
        score_text = Text()

        # Away team line
        away_style = "bold color(38 176 0)" if away_winning and self.game.status in ("LIVE", "HALFTIME") else "bold"
        score_text.append(f"  {away.abbreviation:3}  ", style=away_style)
        score_text.append(f"{self.game.away_score:>3}", style=away_style)
        if away_winning and self.game.status == "FINAL":
            score_text.append(" *", style="color(38 176 0)")
        score_text.append("\n")

        # Home team line
        home_style = "bold color(38 176 0)" if home_winning and self.game.status in ("LIVE", "HALFTIME") else "bold"
        score_text.append(f"  {home.abbreviation:3}  ", style=home_style)
        score_text.append(f"{self.game.home_score:>3}", style=home_style)
        if home_winning and self.game.status == "FINAL":
            score_text.append(" *", style="color(38 176 0)")
        score_text.append("\n")

        # Status line
        if self.game.status == "LIVE":
            score_text.append(f"  {status_text}", style="bold color(38 176 0)")
        elif self.game.status == "HALFTIME":
            score_text.append(f"  {status_text}", style="bold color(255 193 7)")
        elif self.game.status == "FINAL":
            score_text.append(f"  {status_text}", style="dim")
        else:
            score_text.append(f"  {status_text}", style="dim")
        score_text.append("\n")

        # Quarter-by-quarter scoring
        if self.game.away_quarter_scores or self.game.home_quarter_scores:
            score_text.append("\n")
            q_labels = ["Q1", "Q2", "Q3", "Q4"]
            away_q = self.game.away_quarter_scores
            home_q = self.game.home_quarter_scores
            max_q = max(len(away_q), len(home_q))
            for i in range(5, max_q + 1):
                ot = i - 4
                q_labels.append("OT" if ot == 1 else f"{ot}OT")
            q_labels.append("TOT")

            header = f"  {'':3}  " + " ".join(f"{lbl:>3}" for lbl in q_labels)
            away_line = f"  {away.abbreviation:3}  " + " ".join(f"{s:>3}" for s in away_q) + f" {self.game.away_score:>3}"
            home_line = f"  {home.abbreviation:3}  " + " ".join(f"{s:>3}" for s in home_q) + f" {self.game.home_score:>3}"

            score_text.append(header + "\n", style="dim")
            score_text.append(away_line + "\n", style=away_style)
            score_text.append(home_line, style=home_style)

        try:
            score_box = self.query_one("#score-box", Static)
            score_box.update(score_text)
        except Exception:
            pass

    def _render_content(self) -> None:
        """Render the main content area."""
        width = self.size.width
        self._render_stats()
        self._render_pbp()

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
        stats_widget.update("")

    def _render_pbp(self) -> None:
        """Render the play-by-play section."""
        pbp_widget = self.query_one("#pbp-section", Label)
        pbp_widget.update("")

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
        away = self.game.away_team.abbreviation
        home = self.game.home_team.abbreviation
        if self.game.status in ("LIVE", "HALFTIME"):
            self.sub_title = f"{away} @ {home} | Refreshing in {self._countdown}s"
        else:
            self.sub_title = f"{away} @ {home}"

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
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self._countdown = self.refresh_interval
        self._update_subtitle()
        self.client.clear_cache()
        self.run_worker(self._fetch_data())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        self.app.exit()
