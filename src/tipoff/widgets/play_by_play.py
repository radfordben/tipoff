"""Play-by-play widget for NBA games."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from tipoff.api.models import format_period

# Color mapping for event types
EVENT_COLORS = {
    "made_shot": "color(38 176 0)",     # green
    "free_throw": "color(38 176 0)",     # green
    "missed_shot": "dim",                # muted
    "turnover": "color(255 107 107)",    # red
    "foul": "color(255 193 7)",          # amber
    "timeout": "dim",
    "rebound": "dim",
    "substitution": "dim",
    "violation": "color(255 193 7)",
    "period_end": "color(29 66 138)",    # NBA blue
    "start_period": "color(29 66 138)",
}


class PlayByPlay(Widget):
    """Scrollable play-by-play list for NBA games using Rich text rendering."""

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
        color: $text;
        background: $primary;
        padding: 0 1;
    }

    PlayByPlay .pbp-event {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    PlayByPlay .pbp-made-shot {
        color: $success;
        text-style: bold;
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
        text-style: italic;
    }

    PlayByPlay .pbp-rebound {
        color: $text-muted;
    }

    PlayByPlay .pbp-substitution {
        color: $text-muted;
        text-style: italic;
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
            yield Static("No play-by-play data available", classes="pbp-event")
            return

        current_period = None
        for play in reversed(self.plays):
            period = play.get("period", 0)

            # Add period header when period changes
            if period != current_period:
                current_period = period
                period_text = format_period(period)
                if period_text:
                    yield Static(f"  {period_text}  ", classes="pbp-period-header")

            event_type = play.get("event_type", "")
            description = play.get("description", "")
            home_desc = play.get("home_description", "")
            away_desc = play.get("away_description", "")
            clock = play.get("clock", "")
            team = play.get("team", "")

            # Use Rich Text for colored inline rendering
            line = Text()
            line.append(f"{clock:>5} ", style="dim")

            if team:
                line.append(f"{team} ", style="bold")

            # Pick the best description
            event_text = description or home_desc or away_desc or event_type.replace("_", " ")
            color = EVENT_COLORS.get(event_type)
            if color:
                line.append(event_text, style=color)
            else:
                line.append(event_text)

            css_class = EVENT_CSS.get(event_type, "pbp-event")
            yield Static(line, classes=css_class)

    def update_plays(self, plays: list[dict]) -> None:
        """Update the play-by-play data (for live refresh)."""
        self.plays = plays
        self.remove_children()
        for child in self.compose():
            self.mount(child)


# CSS class mapping (for fallback class-based styling)
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
