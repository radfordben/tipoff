"""Play-by-play widget for NBA games."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from tipoff.api.models import format_period

# NBA event type CSS class mapping
EVENT_CSS = {
    "made_shot": "pbp-made-shot",
    "free_throw": "pbp-made-shot",
    "missed_shot": "pbp-missed-shot",
    "turnover": "pbp-turnover",
    "foul": "pbp-foul",
    "timeout": "pbp-timeout",
    "rebound": "pbp-rebound",
    "substitution": "pbp-substitution",
    "period_end": "pbp-period-end",
    "start_period": "pbp-period-end",
    "end_period": "pbp-period-end",
}


class PlayByPlay(Widget):
    """Scrollable play-by-play list for NBA games."""

    DEFAULT_CSS = """
    PlayByPlay {
        width: 100%;
        height: auto;
        max-height: 100%;
    }

    PlayByPlay .pbp-period-header {
        width: 100%;
        height: 1;
        text-align: center;
        text-style: bold;
        color: $primary;
        background: $surface-lighten-1;
    }

    PlayByPlay .pbp-event {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    PlayByPlay .pbp-made-shot {
        color: $success;
    }

    PlayByPlay .pbp-missed-shot {
        color: $text-muted;
    }

    PlayByPlay .pbp-turnover {
        color: $error;
    }

    PlayByPlay .pbp-foul {
        color: $warning;
    }

    PlayByPlay .pbp-timeout {
        color: $text-muted;
    }

    PlayByPlay .pbp-rebound {
        color: $text-muted;
    }

    PlayByPlay .pbp-substitution {
        color: $text-muted;
    }

    PlayByPlay .pbp-period-end {
        color: $primary;
        text-style: bold;
    }
    """

    def __init__(self, plays: list[dict], home_abbrev: str = "", away_abbrev: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.plays = plays
        self.home_abbrev = home_abbrev
        self.away_abbrev = away_abbrev

    def compose(self) -> ComposeResult:
        if not self.plays:
            yield Label("No play-by-play data available", classes="pbp-event")
            return

        # Render in reverse chronological order (most recent first)
        current_period = None
        for play in reversed(self.plays):
            period = play.get("period", 0)

            # Add period header when period changes
            if period != current_period:
                current_period = period
                period_text = format_period(period)
                if period_text:
                    yield Static(f"-- {period_text} --", classes="pbp-period-header")

            event_type = play.get("event_type", "")
            description = play.get("description", "")
            home_desc = play.get("home_description", "")
            away_desc = play.get("away_description", "")
            clock = play.get("clock", "")
            team = play.get("team", "")

            # Build display text
            text = self._format_event(clock, team, event_type, description, home_desc, away_desc)
            css_class = EVENT_CSS.get(event_type, "pbp-event")

            yield Static(text, classes=css_class)

    def _format_event(
        self,
        clock: str,
        team: str,
        event_type: str,
        description: str,
        home_desc: str,
        away_desc: str,
    ) -> str:
        """Format a play-by-play event for display."""
        # Use the most descriptive description available
        event_text = description or home_desc or away_desc or event_type
        if team:
            return f"{clock:>5} {team} {event_text}" if clock else f"     {team} {event_text}"
        return f"{clock:>5} {event_text}" if clock else f"     {event_text}"

    def update_plays(self, plays: list[dict]) -> None:
        """Update the play-by-play data (for live refresh)."""
        self.plays = plays
        self.remove_children()
        for child in self.compose():
            self.mount(child)
