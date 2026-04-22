"""Schedule screen for browsing NBA games."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import ClassVar
from zoneinfo import ZoneInfo

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Header, Label, Static

from tipoff.api import NBAClient
from tipoff.api.models import NBAGame
from tipoff.widgets.game_card import GameCard

# Game card width (34) + margin (1) = 35 chars per card
CARD_WIDTH = 35

# NBA uses Eastern Time for scheduling
NBA_TIMEZONE = ZoneInfo("America/New_York")


def get_nba_today() -> date:
    """Get the current date in NBA timezone (Eastern Time)."""
    return datetime.now(NBA_TIMEZONE).date()


class ScheduleScreen(Screen):
    """Screen for viewing the NBA game schedule."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("h", "prev_day", "Prev Day"),
        Binding("l", "next_day", "Next Day"),
        Binding("t", "today", "Today"),
        Binding("b", "bracket", "Bracket"),
        Binding("s", "standings", "Standings"),
        Binding("p", "stats", "Stats"),
        Binding("m", "teams", "Teams"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
        Binding("left", "focus_prev_card", "Previous Game", show=False),
        Binding("right", "focus_next_card", "Next Game", show=False),
        Binding("up", "focus_card_above", "Game Above", show=False),
        Binding("down", "focus_card_below", "Game Below", show=False),
    ]

    DEFAULT_CSS = """
    ScheduleScreen {
        background: $surface;
    }

    ScheduleScreen .date-header {
        width: 100%;
        height: 3;
        align: center middle;
        text-style: bold;
        color: $accent;
        border-bottom: wide $primary;
    }

    ScheduleScreen .date-nav {
        width: 100%;
        height: 1;
        align: center middle;
        color: $text-muted;
        text-style: italic;
    }

    ScheduleScreen .games-scroll {
        width: 100%;
        height: 1fr;
        padding: 1 1;
    }

    ScheduleScreen .games-grid {
        width: 100%;
        height: auto;
    }

    ScheduleScreen .games-row {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    ScheduleScreen .no-games {
        width: 100%;
        height: auto;
        padding: 2;
        text-align: center;
        color: $text-muted;
        text-style: italic;
    }

    ScheduleScreen .loading {
        width: 100%;
        height: auto;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, refresh_interval: int = 30, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.refresh_interval = refresh_interval
        self.current_date = get_nba_today()
        self._use_nba_today = True  # Start by fetching ESPN's "now"
        self.games: list[NBAGame] = []
        self._refresh_timer: Timer | None = None
        self._countdown_timer: Timer | None = None
        self._countdown: int = refresh_interval
        self._last_width: int = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._format_date(), classes="date-header", id="date-header")
        yield Static(
            "h/l: Date  t: Today  b: Bracket  s: Standings  p: Stats  m: Teams  r: Refresh  q: Quit",
            classes="date-nav",
        )
        with VerticalScroll(classes="games-scroll", id="games-scroll"), Vertical(classes="games-grid", id="games-grid"):
            yield Label("Loading...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load games when the screen is mounted."""
        self.load_games()
        self._countdown = self.refresh_interval
        self._refresh_timer = self.set_interval(self.refresh_interval, callback=self._auto_refresh)
        self._countdown_timer = self.set_interval(1, callback=self._update_countdown)
        self._update_subtitle()

    def on_unmount(self) -> None:
        """Clean up when screen is unmounted."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._countdown_timer:
            self._countdown_timer.stop()

    def _format_date(self) -> str:
        """Format the current date for display."""
        today = get_nba_today()
        if self.current_date == today:
            day_label = "Today"
        elif self.current_date == today - timedelta(days=1):
            day_label = "Yesterday"
        elif self.current_date == today + timedelta(days=1):
            day_label = "Tomorrow"
        else:
            day_label = self.current_date.strftime("%A")

        return f"{day_label} - {self.current_date.strftime('%B %d, %Y')}"

    def load_games(self) -> None:
        """Load games for the current date."""
        self.run_worker(self._fetch_games())

    async def _fetch_games(self) -> None:
        """Fetch games from the ESPN API."""
        try:
            if self._use_nba_today:
                # No date = ESPN returns current day's games (handles after-midnight)
                self.games = await self.client.get_scoreboard()
                # Sync our date to whatever ESPN returned
                if self.client._last_scoreboard_date:
                    date_str = self.client._last_scoreboard_date
                    self.current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    self._use_nba_today = False
            else:
                date_str = self.current_date.strftime("%Y%m%d")
                self.games = await self.client.get_scoreboard(date_str)
            self._update_games_display()
        except Exception as e:
            self.notify(f"Error loading games: {e}", severity="error")

    def _get_cards_per_row(self) -> int:
        """Calculate how many cards fit per row based on container width."""
        try:
            scroll = self.query_one("#games-scroll", VerticalScroll)
            available_width = scroll.size.width - 4
            cards_per_row = max(1, available_width // CARD_WIDTH)
        except Exception:
            return 2
        else:
            return cards_per_row

    def _update_games_display(self) -> None:
        """Update the games container with loaded games."""
        grid = self.query_one("#games-grid", Vertical)
        grid.remove_children()

        # Update date header
        date_header = self.query_one("#date-header", Static)
        date_header.update(self._format_date())

        if not self.games:
            grid.mount(Label("No games scheduled", classes="no-games"))
            return

        cards_per_row = self._get_cards_per_row()

        # Create rows of game cards
        for i in range(0, len(self.games), cards_per_row):
            row_games = self.games[i : i + cards_per_row]
            row = Horizontal(classes="games-row")
            grid.mount(row)
            for game in row_games:
                card = GameCard(game)
                row.mount(card)

        # Focus the first game card
        cards = self.query(GameCard)
        if cards:
            cards[0].focus()

    def on_resize(self, event) -> None:
        """Handle terminal resize to reflow game cards."""
        if not self.games:
            return
        try:
            scroll = self.query_one("#games-scroll", VerticalScroll)
            new_width = scroll.size.width
        except Exception:
            return
        if abs(new_width - self._last_width) >= CARD_WIDTH:
            self._last_width = new_width
            self._update_games_display()

    def _update_countdown(self) -> None:
        """Update the countdown timer every second."""
        self._countdown -= 1
        if self._countdown < 0:
            self._countdown = self.refresh_interval
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        """Update the screen subtitle with countdown (only for today)."""
        if self.current_date == get_nba_today():
            self.sub_title = f"Refreshing in {self._countdown}s"
        else:
            self.sub_title = ""

    def _auto_refresh(self) -> None:
        """Auto-refresh games (for live updates)."""
        self._countdown = self.refresh_interval
        # Auto-refresh when viewing ESPN's "now" or calendar today
        nba_today = get_nba_today()
        if self.current_date == nba_today or self._use_nba_today:
            self._update_subtitle()
            self.client.clear_cache()
            self.load_games()

    def on_game_card_selected(self, event: GameCard.Selected) -> None:
        """Handle game card selection."""
        game = event.game

        if game.status == "PPD":
            self.notify("This game has been postponed", severity="warning")
            return
        if game.status == "CNCL":
            self.notify("This game has been cancelled", severity="warning")
            return

        if game.status == "FUT":
            from tipoff.screens.pregame import PreGameScreen

            self.app.push_screen(PreGameScreen(client=self.client, game=game))
            return

        from tipoff.screens.game import GameScreen

        self.app.push_screen(GameScreen(client=self.client, game=game, refresh_interval=self.refresh_interval))

    def action_prev_day(self) -> None:
        """Go to previous day."""
        self._use_nba_today = False
        self.current_date -= timedelta(days=1)
        self._update_subtitle()
        self.load_games()

    def action_next_day(self) -> None:
        """Go to next day."""
        self._use_nba_today = False
        self.current_date += timedelta(days=1)
        self._update_subtitle()
        self.load_games()

    def action_today(self) -> None:
        """Go to today (ESPN's current day)."""
        self._use_nba_today = True
        self._countdown = self.refresh_interval
        self._update_subtitle()
        self.load_games()

    def action_refresh(self) -> None:
        """Manually refresh games."""
        self._countdown = self.refresh_interval
        self._update_subtitle()
        self.client.clear_cache()
        self.load_games()
        self.notify("Refreshed")

    def action_bracket(self) -> None:
        """Show playoff bracket screen."""
        from tipoff.screens.bracket import BracketScreen

        self.app.push_screen(BracketScreen(client=self.client))

    def action_standings(self) -> None:
        """Show standings screen."""
        from tipoff.screens.standings import StandingsScreen

        self.app.push_screen(StandingsScreen(client=self.client))

    def action_stats(self) -> None:
        """Show stats screen."""
        from tipoff.screens.stats import StatsScreen

        self.app.push_screen(StatsScreen(client=self.client))

    def action_teams(self) -> None:
        """Show teams screen."""
        from tipoff.screens.teams import TeamsScreen

        self.app.push_screen(TeamsScreen(client=self.client))

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def _get_focused_card_index(self) -> int:
        """Get the index of the currently focused card, or -1 if none."""
        cards = list(self.query(GameCard))
        for i, card in enumerate(cards):
            if card.has_focus:
                return i
        return -1

    def _focus_card_at_index(self, index: int) -> None:
        """Focus the card at the given index."""
        cards = list(self.query(GameCard))
        if cards and 0 <= index < len(cards):
            cards[index].focus()

    def action_focus_prev_card(self) -> None:
        """Focus the previous game card."""
        idx = self._get_focused_card_index()
        if idx > 0:
            self._focus_card_at_index(idx - 1)
        elif idx == -1:
            self._focus_card_at_index(0)

    def action_focus_next_card(self) -> None:
        """Focus the next game card."""
        idx = self._get_focused_card_index()
        cards = list(self.query(GameCard))
        if idx < len(cards) - 1:
            self._focus_card_at_index(idx + 1)

    def action_focus_card_above(self) -> None:
        """Focus the game card above (previous row, same column)."""
        idx = self._get_focused_card_index()
        if idx < 0:
            return
        cards_per_row = self._get_cards_per_row()
        new_idx = idx - cards_per_row
        if new_idx >= 0:
            self._focus_card_at_index(new_idx)

    def action_focus_card_below(self) -> None:
        """Focus the game card below (next row, same column)."""
        idx = self._get_focused_card_index()
        if idx < 0:
            return
        cards = list(self.query(GameCard))
        cards_per_row = self._get_cards_per_row()
        new_idx = idx + cards_per_row
        if new_idx < len(cards):
            self._focus_card_at_index(new_idx)
