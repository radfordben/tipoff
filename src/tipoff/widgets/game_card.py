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
        width: 34;
        height: 7;
        border: round $primary;
        padding: 0 1;
        margin: 0 1 1 0;
        background: $surface;
    }

    GameCard:hover {
        border: round $secondary;
        background: $surface-lighten-1;
    }

    GameCard:focus {
        border: double $accent;
    }

    GameCard.-live {
        border: round $success;
        background: $surface-darken-1;
    }

    GameCard.-live:focus {
        border: double $accent;
    }

    GameCard.-final {
        border: round $surface-lighten-2;
        background: $surface;
    }

    GameCard.-final:focus {
        border: double $accent;
    }

    GameCard.-halftime {
        border: round $warning;
    }

    GameCard .team-row {
        width: 100%;
        height: 1;
    }

    GameCard .team-abbr {
        width: 4;
        text-style: bold;
    }

    GameCard .team-city {
        width: 1fr;
        color: $text-muted;
    }

    GameCard .team-score {
        width: 4;
        text-align: right;
        text-style: bold;
    }

    GameCard .game-status {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
        text-style: italic;
    }

    GameCard.-live .game-status {
        color: $success;
        text-style: bold;
    }

    GameCard.-halftime .game-status {
        color: $warning;
        text-style: bold;
    }

    GameCard.-final .game-status {
        color: $text-muted;
    }

    GameCard .series-info {
        width: 100%;
        height: 1;
        text-align: center;
        color: $accent;
    }

    GameCard .winning {
        color: $success;
    }

    GameCard .broadcast {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
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
        away = self.game.away_team
        home = self.game.home_team
        show_score = self.game.status not in ("FUT",)

        away_score = str(self.game.away_score) if show_score else ""
        home_score = str(self.game.home_score) if show_score else ""
        away_winning = show_score and self.game.away_score > self.game.home_score
        home_winning = show_score and self.game.home_score > self.game.away_score

        with Vertical():
            # Away team row
            with Horizontal(classes="team-row"):
                yield Label(away.abbreviation or "???", classes="team-abbr")
                yield Label(away.city or "", classes="team-city")
                score_class = "team-score winning" if away_winning else "team-score"
                yield Label(away_score, classes=score_class)

            # Home team row
            with Horizontal(classes="team-row"):
                yield Label(home.abbreviation or "???", classes="team-abbr")
                yield Label(home.city or "", classes="team-city")
                score_class = "team-score winning" if home_winning else "team-score"
                yield Label(home_score, classes=score_class)

            # Status line
            yield Static(self._get_status_text(), classes="game-status")

            # Series info
            if self.game.series and self.game.series.summary:
                yield Static(self.game.series.summary, classes="series-info")
            else:
                yield Static("", classes="series-info")

            # Broadcast info
            if self.game.broadcasts:
                yield Static(", ".join(self.game.broadcasts[:2]), classes="broadcast")

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
