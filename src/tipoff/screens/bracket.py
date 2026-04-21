"""Playoff bracket screen for NBA playoffs."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Label, Static

from tipoff.api import NBAClient
from tipoff.api.models import NBASeries

BRACKET_SIDE_BY_SIDE_MIN_WIDTH = 150


class SeriesCard(Widget):
    """A clickable card showing a playoff series matchup."""

    DEFAULT_CSS = """
    SeriesCard {
        width: 28;
        height: auto;
        min-height: 3;
        border: solid $primary;
        padding: 0 1;
        margin: 0 1 1 0;
    }

    SeriesCard:hover {
        border: solid $secondary;
    }

    SeriesCard:focus {
        border: double $accent;
    }

    SeriesCard.-completed {
        border: solid $surface;
    }

    SeriesCard.-live {
        border: solid $success;
    }

    SeriesCard .series-team {
        width: 100%;
        height: 1;
    }

    SeriesCard .series-status {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
    }

    SeriesCard.-live .series-status {
        color: $success;
    }

    SeriesCard .seed {
        width: 3;
        color: $text-muted;
    }

    SeriesCard .team-abbr {
        width: 1fr;
    }

    SeriesCard .wins {
        width: 2;
        text-align: right;
    }

    SeriesCard .winning {
        color: $success;
        text-style: bold;
    }
    """

    can_focus = True

    class Selected(Message):
        """Message sent when a series card is selected."""

        def __init__(self, series: NBASeries) -> None:
            self.series = series
            super().__init__()

    def __init__(self, series: NBASeries, **kwargs) -> None:
        super().__init__(**kwargs)
        self.series = series

    def compose(self) -> ComposeResult:
        higher = self.series.higher_seed
        lower = self.series.lower_seed

        higher_wins = self.series.higher_seed_wins
        lower_wins = self.series.lower_seed_wins

        higher_class = "winning" if higher_wins > lower_wins else ""
        lower_class = "winning" if lower_wins > higher_wins else ""

        with Horizontal(classes="series-team"):
            yield Label(f"{higher.seed or '':>2}", classes="seed")
            yield Label(higher.abbreviation or "???", classes="team-abbr")
            yield Label(str(higher_wins), classes=f"wins {higher_class}")

        with Horizontal(classes="series-team"):
            yield Label(f"{lower.seed or '':>2}", classes="seed")
            yield Label(lower.abbreviation or "???", classes="team-abbr")
            yield Label(str(lower_wins), classes=f"wins {lower_class}")

        status_text = self.series.summary or self._get_status_text()
        yield Static(status_text, classes="series-status")

    def _get_status_text(self) -> str:
        """Get the series status text."""
        if self.series.completed:
            return "Completed"
        if self.series.higher_seed_wins > 0 or self.series.lower_seed_wins > 0:
            return "In Progress"
        return "Upcoming"

    def on_mount(self) -> None:
        """Apply CSS classes based on series status."""
        if self.series.completed:
            self.add_class("-completed")
        elif self.series.higher_seed_wins > 0 or self.series.lower_seed_wins > 0:
            self.add_class("-live")

    def on_click(self) -> None:
        """Handle click event."""
        self.post_message(self.Selected(self.series))

    def on_key(self, event) -> None:
        """Handle key event."""
        if event.key == "enter":
            self.post_message(self.Selected(self.series))
            event.stop()


class BracketWidget(Widget):
    """Renders the playoff bracket layout."""

    DEFAULT_CSS = """
    BracketWidget {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    BracketWidget .round-header {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    BracketWidget .round-section {
        width: 100%;
        height: auto;
        margin-bottom: 2;
    }

    BracketWidget .round-series {
        width: 100%;
        height: auto;
    }

    BracketWidget .conference-label {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(self, series_list: list[NBASeries], **kwargs) -> None:
        super().__init__(**kwargs)
        self.series_list = series_list

    def compose(self) -> ComposeResult:
        if not self.series_list:
            yield Label("No playoff bracket data available", classes="no-data")
            return

        # Group by round and conference
        rounds: dict[int, dict[str, list[NBASeries]]] = {}
        for s in self.series_list:
            round_num = s.round_num or 1
            conf = s.conference or "League"
            if round_num not in rounds:
                rounds[round_num] = {}
            if conf not in rounds[round_num]:
                rounds[round_num][conf] = []
            rounds[round_num][conf].append(s)

        round_names = {1: "First Round", 2: "Conf. Semifinals", 3: "Conf. Finals", 4: "NBA Finals"}

        for round_num in sorted(rounds.keys()):
            round_label = round_names.get(round_num, f"Round {round_num}")
            yield Static(f"── {round_label} ──", classes="round-header")
            with Vertical(classes="round-section"):
                for conf_name in ("Eastern", "Western", "League"):
                    if conf_name not in rounds[round_num]:
                        continue
                    if conf_name != "League" and len(rounds[round_num]) > 1:
                        yield Static(f"  {conf_name} Conference", classes="conference-label")
                    with Horizontal(classes="round-series"):
                        for series in rounds[round_num][conf_name]:
                            yield SeriesCard(series)


class BracketScreen(Screen):
    """Screen for viewing the NBA playoff bracket."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    BracketScreen {
        background: $surface;
    }

    BracketScreen .bracket-title {
        width: 100%;
        height: 3;
        align: center middle;
        text-style: bold;
        border-bottom: solid $primary;
    }

    BracketScreen .bracket-scroll {
        width: 100%;
        height: 1fr;
    }

    BracketScreen .loading {
        width: 100%;
        height: auto;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.series_list: list[NBASeries] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("NBA Playoff Bracket", classes="bracket-title", id="bracket-title")
        with VerticalScroll(classes="bracket-scroll", id="bracket-scroll"):
            yield Label("Loading bracket...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load bracket data."""
        self.run_worker(self._fetch_bracket())

    async def _fetch_bracket(self) -> None:
        """Fetch playoff bracket data."""
        try:
            # Get today's games which include series data
            games = await self.client.get_scoreboard()

            # Extract unique series from games
            seen_series_ids: set[str] = set()
            self.series_list = []
            for game in games:
                if game.series and game.series.id not in seen_series_ids:
                    seen_series_ids.add(game.series.id)
                    self.series_list.append(game.series)

            self._render_bracket()
        except Exception as e:
            self.notify(f"Error loading bracket: {e}", severity="error")

    def _render_bracket(self) -> None:
        """Render the bracket widget."""
        scroll = self.query_one("#bracket-scroll", VerticalScroll)
        scroll.remove_children()

        bracket = BracketWidget(self.series_list)
        scroll.mount(bracket)

    def on_series_card_selected(self, event: SeriesCard.Selected) -> None:
        """Handle series card selection."""
        from tipoff.screens.series import SeriesDetailScreen

        self.app.push_screen(SeriesDetailScreen(client=self.client, series=event.series))

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Manually refresh the bracket."""
        self.client.clear_cache()
        self.run_worker(self._fetch_bracket())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
