"""Game card widget for displaying a single NBA game in the schedule."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static

from tipoff.api.models import NBAGame, format_period_short


def get_local_time_with_tz(iso_time: str) -> str:
    """Convert ISO time string to local time with timezone abbreviation."""
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


class GameCard(Widget):
    """A card widget displaying a single NBA game's status."""

    DEFAULT_CSS = """
    GameCard {
        width: 28;
        height: 6;
        border: solid $primary;
        padding: 0 1;
        margin: 0 1 0 0;
    }

    GameCard:hover {
        border: solid $secondary;
    }

    GameCard:focus {
        border: double $accent;
    }

    GameCard.-live {
        border: solid $success;
    }

    GameCard.-live:focus {
        border: double $accent;
    }

    GameCard.-final {
        border: solid $surface;
    }

    GameCard.-final:focus {
        border: double $accent;
    }

    GameCard.-halftime {
        border: solid $warning;
    }

    GameCard .team-row {
        width: 100%;
        height: 1;
    }

    GameCard .team-name {
        width: 1fr;
    }

    GameCard .team-score {
        width: 3;
        text-align: right;
    }

    GameCard .game-status {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
    }

    GameCard.-live .game-status {
        color: $success;
    }

    GameCard.-halftime .game-status {
        color: $warning;
    }

    GameCard .series-info {
        width: 100%;
        height: 1;
        text-align: center;
        color: $accent;
        text-style: italic;
    }
    """

    can_focus = True

    class Selected(Message):
        """Message sent when a game card is selected."""

        def __init__(self, game: NBAGame) -> None:
            self.game = game
            super().__init__()

    def __init__(self, game: NBAGame, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game = game

    def compose(self) -> ComposeResult:
        away_abbrev = self.game.away_team.abbreviation or "???"
        home_abbrev = self.game.home_team.abbreviation or "???"

        show_score = self.game.status not in ("FUT",)

        away_score = str(self.game.away_score) if show_score and self.game.away_score is not None else ""
        home_score = str(self.game.home_score) if show_score and self.game.home_score is not None else ""

        status = self._get_status_text()

        with Vertical():
            with Horizontal(classes="team-row"):
                yield Label(away_abbrev, classes="team-name")
                yield Label(away_score, classes="team-score")
            with Horizontal(classes="team-row"):
                yield Label(home_abbrev, classes="team-name")
                yield Label(home_score, classes="team-score")
            yield Static(status, classes="game-status")
            # Show series info during playoffs
            if self.game.series and self.game.series.summary:
                yield Static(self.game.series.summary, classes="series-info")
            else:
                yield Static("", classes="series-info")

    def _get_status_text(self) -> str:
        """Get the status text for the game."""
        status = self.game.status

        if status == "PPD":
            return "Postponed"
        if status == "CNCL":
            return "Cancelled"

        if status == "FUT":
            local_time = get_local_time_with_tz(self.game.date)
            return local_time if local_time else "Scheduled"

        if status == "HALFTIME":
            return "Halftime"

        if status == "LIVE":
            period_str = format_period_short(self.game.period)
            if period_str and self.game.clock:
                return f"{period_str} {self.game.clock}"
            if period_str:
                return period_str
            return "Live"

        if status == "FINAL":
            if self.game.period > 4:
                ot_label = "OT" if self.game.period == 5 else f"{self.game.period - 4}OT"
                return f"Final/{ot_label}"
            return "Final"

        return status

    def on_mount(self) -> None:
        """Apply CSS classes based on game state."""
        if self.game.status == "LIVE":
            self.add_class("-live")
        elif self.game.status == "HALFTIME":
            self.add_class("-halftime")
        elif self.game.status == "FINAL":
            self.add_class("-final")

    def on_click(self) -> None:
        """Handle click event."""
        self.post_message(self.Selected(self.game))

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "enter":
            self.post_message(self.Selected(self.game))
            event.stop()
