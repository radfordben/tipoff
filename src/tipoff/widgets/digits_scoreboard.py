"""Digits scoreboard widget for large LED-style score display."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Digits, Label, Static

from tipoff.api.models import NBAGame, format_period_short


class DigitsScoreboard(Widget):
    """Large LED-style score display using Textual's Digits widget."""

    DEFAULT_CSS = """
    DigitsScoreboard {
        width: 100%;
        height: auto;
        padding: 1 2;
        background: $surface;
    }

    DigitsScoreboard .score-row {
        width: 100%;
        height: auto;
        align: center middle;
    }

    DigitsScoreboard .team-label {
        width: 1fr;
        text-align: right;
        padding: 0 2;
        text-style: bold;
    }

    DigitsScoreboard .score-digits {
        width: auto;
        padding: 0 1;
    }

    DigitsScoreboard .status-line {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
    }

    DigitsScoreboard.-live .status-line {
        color: $success;
    }

    DigitsScoreboard.-halftime .status-line {
        color: $warning;
    }

    DigitsScoreboard .series-line {
        width: 100%;
        height: 1;
        text-align: center;
        color: $accent;
        text-style: italic;
    }

    DigitsScoreboard .quarter-scores {
        width: 100%;
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    """

    def __init__(self, game: NBAGame, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game = game

    def compose(self) -> ComposeResult:
        # Away team row: label + score
        with Horizontal(classes="score-row"):
            yield Label(self.game.away_team.abbreviation, classes="team-label")
            yield Digits(str(self.game.away_score), classes="score-digits", id="away-score")

        # Home team row: label + score
        with Horizontal(classes="score-row"):
            yield Label(self.game.home_team.abbreviation, classes="team-label")
            yield Digits(str(self.game.home_score), classes="score-digits", id="home-score")

        # Status line
        status = self._get_status_text()
        yield Static(status, classes="status-line", id="game-status")

        # Series info (playoffs)
        series_text = self.game.series.summary if self.game.series else ""
        yield Static(series_text, classes="series-line", id="series-info")

        # Quarter-by-quarter scores if available
        if self.game.home_quarter_scores or self.game.away_quarter_scores:
            yield Static(self._format_quarter_scores(), classes="quarter-scores", id="quarter-scores")

    def _get_status_text(self) -> str:
        """Get the status text for the game."""
        from tipoff.api.models import format_period

        status = self.game.status
        if status == "FUT":
            return get_local_time_with_tz(self.game.date) or "Scheduled"
        if status == "HALFTIME":
            return "Halftime"
        if status == "LIVE":
            p = format_period(self.game.period)
            if p and self.game.clock:
                return f"{p} - {self.game.clock}"
            if p:
                return p
            return "Live"
        if status == "FINAL":
            p = format_period(self.game.period)
            return "Final" + (f"/{format_period_short(self.game.period)}" if self.game.period > 4 else "")
        return status

    def _format_quarter_scores(self) -> str:
        """Format quarter-by-quarter scores as a table."""
        headers = ["  ", "1", "2", "3", "4"]
        away_scores = self.game.away_quarter_scores
        home_scores = self.game.home_quarter_scores

        # Add OT columns if needed
        max_quarters = max(len(away_scores), len(home_scores))
        if max_quarters > 4:
            for i in range(5, max_quarters + 1):
                ot_num = i - 4
                headers.append(f"OT{ot_num}" if ot_num > 1 else "OT")

        headers.append("T")
        line = "  ".join(headers)
        away_row = f"{self.game.away_team.abbreviation:3}" + " ".join(
            f"{s:2}" for s in away_scores
        ) + f" {self.game.away_score:3}"
        home_row = f"{self.game.home_team.abbreviation:3}" + " ".join(
            f"{s:2}" for s in home_scores
        ) + f" {self.game.home_score:3}"

        return f"{line}\n{away_row}\n{home_row}"

    def update_game(self, game: NBAGame) -> None:
        """Update the display with new game data."""
        self.game = game
        try:
            away_score = self.query_one("#away-score", Digits)
            away_score.update(str(game.away_score))
            home_score = self.query_one("#home-score", Digits)
            home_score.update(str(game.home_score))
            status = self.query_one("#game-status", Static)
            status.update(self._get_status_text())
            series = self.query_one("#series-info", Static)
            series.update(game.series.summary if game.series else "")
        except Exception:
            pass


def get_local_time_with_tz(iso_time: str) -> str:
    """Convert ISO time string to local time with timezone."""
    from datetime import datetime

    if not iso_time:
        return ""
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        dt_local = dt.astimezone()
        time_str = dt_local.strftime("%I:%M %p").lstrip("0")
        tz_abbrev = dt_local.strftime("%Z")
        if not tz_abbrev or tz_abbrev == dt_local.strftime("%z"):
            offset = dt_local.strftime("%z")
            if offset and len(offset) >= 5:
                tz_abbrev = f"UTC{offset[:3]}:{offset[3:]}"
            elif offset:
                tz_abbrev = f"UTC{offset}"
            else:
                tz_abbrev = "UTC"
    except (ValueError, AttributeError, IndexError):
        return ""
    else:
        return f"{time_str} {tz_abbrev}"
