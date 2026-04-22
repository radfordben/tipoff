"""Teams screen for browsing NBA teams and rosters."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Header, Label, Static

from tipoff.api import NBAClient
from tipoff.api.models import NBATeam

TEAM_CARD_WIDTH = 13


class TeamCard(Widget):
    """A clickable card showing a team abbreviation."""

    DEFAULT_CSS = """
    TeamCard {
        width: 12;
        height: 3;
        border: solid $primary;
        padding: 0 1;
        margin: 0 1 1 0;
        content-align: center middle;
    }

    TeamCard:hover {
        border: solid $secondary;
    }

    TeamCard:focus {
        border: double $accent;
    }
    """

    can_focus = True

    class Selected(Message):
        """Message sent when a team card is selected."""

        def __init__(self, team: NBATeam) -> None:
            self.team = team
            super().__init__()

    def __init__(self, team: NBATeam, **kwargs) -> None:
        super().__init__(**kwargs)
        self.team = team

    def compose(self) -> ComposeResult:
        yield Label(self.team.abbreviation or "???")

    def on_click(self) -> None:
        self.post_message(self.Selected(self.team))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Selected(self.team))
            event.stop()


class PlayerRow(Widget):
    """A clickable row showing a player's number, name, and position."""

    DEFAULT_CSS = """
    PlayerRow {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    PlayerRow:hover {
        background: $surface-lighten-1;
    }

    PlayerRow .player-num {
        width: 4;
        color: $text-muted;
    }

    PlayerRow .player-name {
        width: 1fr;
    }

    PlayerRow .player-pos {
        width: 4;
        color: $text-muted;
    }
    """

    can_focus = True

    class Selected(Message):
        """Message sent when a player row is selected."""

        def __init__(self, player_id: str, player_name: str) -> None:
            self.player_id = player_id
            self.player_name = player_name
            super().__init__()

    def __init__(self, player_id: str, player_name: str, number: str, position: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.player_id = player_id
        self.player_name = player_name
        self.number = number
        self.position = position

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"#{self.number}", classes="player-num")
            yield Label(self.player_name, classes="player-name")
            yield Label(self.position, classes="player-pos")

    def on_click(self) -> None:
        self.post_message(self.Selected(self.player_id, self.player_name))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Selected(self.player_id, self.player_name))
            event.stop()


class TeamsScreen(Screen):
    """Screen for browsing NBA teams."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    TeamsScreen {
        background: $surface;
    }

    TeamsScreen .teams-title {
        width: 100%;
        height: 3;
        align: center middle;
        text-style: bold;
        border-bottom: solid $primary;
    }

    TeamsScreen .conference-label {
        width: 100%;
        height: 1;
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin: 1 0;
    }

    TeamsScreen .teams-grid {
        width: 100%;
        height: auto;
    }

    TeamsScreen .teams-row {
        width: 100%;
        height: auto;
    }

    TeamsScreen .loading {
        width: 100%;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self._teams: list[NBATeam] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("NBA Teams", classes="teams-title")
        with VerticalScroll(id="teams-scroll"):
            yield Label("Loading teams...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load teams data."""
        self.run_worker(self._fetch_teams())

    async def _fetch_teams(self) -> None:
        """Fetch teams from ESPN API."""
        try:
            self._teams = await self.client.get_teams()
            self._render_teams()
        except Exception as e:
            self.notify(f"Error loading teams: {e}", severity="error")

    def _render_teams(self) -> None:
        """Render the teams grid grouped by conference."""
        scroll = self.query_one("#teams-scroll", VerticalScroll)
        scroll.remove_children()

        if not self._teams:
            scroll.mount(Label("No teams data available", classes="loading"))
            return

        east_teams = [t for t in self._teams if t.conference == "Eastern"]
        west_teams = [t for t in self._teams if t.conference == "Western"]

        for label, teams in [("Eastern Conference", east_teams), ("Western Conference", west_teams)]:
            if not teams:
                continue
            scroll.mount(Static(f"── {label} ──", classes="conference-label"))
            with Horizontal(classes="teams-row"):
                for team in sorted(teams, key=lambda t: t.name):
                    scroll.mount(TeamCard(team))
                    # We need to mount into the horizontal, not the scroll
                    # Let me restructure this

        # Actually let's just use a simpler layout
        scroll.remove_children()

        for label, teams in [("Eastern Conference", east_teams), ("Western Conference", west_teams)]:
            if not teams:
                continue
            scroll.mount(Static(f"── {label} ──", classes="conference-label"))

            cards_per_row = max(1, (self.size.width - 4) // TEAM_CARD_WIDTH)

            sorted_teams = sorted(teams, key=lambda t: t.name)
            for i in range(0, len(sorted_teams), cards_per_row):
                row_teams = sorted_teams[i : i + cards_per_row]
                row = Horizontal(classes="teams-row")
                scroll.mount(row)
                for team in row_teams:
                    row.mount(TeamCard(team))

        # Focus first card
        cards = self.query(TeamCard)
        if cards:
            cards[0].focus()

    def on_team_card_selected(self, event: TeamCard.Selected) -> None:
        """Handle team card selection."""
        self.app.push_screen(TeamDetailScreen(client=self.client, team=event.team))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.client.clear_cache()
        self.run_worker(self._fetch_teams())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        self.app.exit()


class TeamDetailScreen(Screen):
    """Screen showing team details (roster and schedule)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("1", "show_roster", "Roster"),
        Binding("2", "show_schedule", "Schedule"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    TeamDetailScreen {
        background: $surface;
    }

    TeamDetailScreen .team-header {
        width: 100%;
        height: 3;
        align: center middle;
        text-style: bold;
        border-bottom: solid $primary;
    }

    TeamDetailScreen .section-title {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    TeamDetailScreen .position-label {
        width: 100%;
        height: 1;
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    TeamDetailScreen .loading {
        width: 100%;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, team: NBATeam, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.team = team
        self._current_tab = "roster"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"{self.team.name}", classes="team-header", id="team-title")
        with VerticalScroll(id="team-content"):
            yield Label("Loading...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load team data."""
        self.run_worker(self._fetch_roster())

    async def _fetch_roster(self) -> None:
        """Fetch team roster."""
        try:
            from tipoff.api import nba_stats

            self._players = await nba_stats.get_team_roster(self.team.id)
            self._render_roster()
        except Exception as e:
            self.notify(f"Error loading roster: {e}", severity="error")

    def _render_roster(self) -> None:
        """Render the team roster grouped by position."""
        content = self.query_one("#team-content", VerticalScroll)
        content.remove_children()

        if not self._players:
            content.mount(Label("No roster data available", classes="loading"))
            return

        # Group by position category
        guards = [p for p in self._players if p.position in ("PG", "SG", "G")]
        forwards = [p for p in self._players if p.position in ("SF", "PF", "F")]
        centers = [p for p in self._players if p.position == "C"]

        for group_name, group_players in [("Guards", guards), ("Forwards", forwards), ("Centers", centers)]:
            if not group_players:
                continue
            content.mount(Static(f"── {group_name} ──", classes="position-label"))
            for player in sorted(group_players, key=lambda p: p.number or 0):
                content.mount(
                    PlayerRow(
                        player_id=player.id,
                        player_name=player.name,
                        number=str(player.number or ""),
                        position=player.position,
                    )
                )

    def on_player_row_selected(self, event: PlayerRow.Selected) -> None:
        """Handle player selection."""
        from tipoff.screens.player import PlayerScreen

        self.app.push_screen(PlayerScreen(client=self.client, player_id=event.player_id, player_name=event.player_name))

    def action_show_roster(self) -> None:
        self._current_tab = "roster"
        self.run_worker(self._fetch_roster())

    def action_show_schedule(self) -> None:
        self._current_tab = "schedule"
        self.run_worker(self._fetch_schedule())

    async def _fetch_schedule(self) -> None:
        """Fetch team schedule."""
        try:
            data = await self.client.get_team_schedule(self.team.id)
            self._render_schedule(data)
        except Exception as e:
            self.notify(f"Error loading schedule: {e}", severity="error")

    def _render_schedule(self, data: dict) -> None:
        """Render the team schedule."""
        content = self.query_one("#team-content", VerticalScroll)
        content.remove_children()

        content.mount(Static("── Schedule ──", classes="section-title"))

        events = data.get("events", [])
        if not events:
            content.mount(Label("No schedule data available", classes="loading"))
            return

        table = DataTable(id="schedule-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Date", "Opponent", "Result")

        for event in events[:20]:  # Show last/next 20 games
            date_str = event.get("date", "")[:10]
            name = event.get("name", "")
            competitions = event.get("competitions", [])
            result = "-"
            if competitions:
                comp = competitions[0]
                for competitor in comp.get("competitors", []):
                    if competitor.get("homeAway") == "home":
                        result = competitor.get("score", "-")
            table.add_row(date_str, name, result)

        content.mount(table)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.client.clear_cache()
        if self._current_tab == "roster":
            self.run_worker(self._fetch_roster())
        else:
            self.run_worker(self._fetch_schedule())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        self.app.exit()
