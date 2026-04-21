"""Standings screen for NBA conference standings."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from tipoff.api import NBAClient

SIDE_BY_SIDE_MIN_WIDTH = 150


class StandingsScreen(Screen):
    """Screen for viewing NBA standings."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,b", "back", "Back"),
        Binding("1", "show_conference", "Conference"),
        Binding("2", "show_playoff_race", "Playoff Race"),
        Binding("3", "show_league", "League"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    StandingsScreen {
        background: $surface;
    }

    StandingsScreen .standings-title {
        width: 100%;
        height: 3;
        align: center middle;
        text-style: bold;
        border-bottom: solid $primary;
    }

    StandingsScreen .standings-scroll {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    StandingsScreen .tab-hint {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
    }

    StandingsScreen .conference-label {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    StandingsScreen .loading {
        width: 100%;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, client: NBAClient, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self._current_tab = "conference"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("NBA Standings", classes="standings-title", id="standings-title")
        yield Static("1: Conference | 2: Playoff Race | 3: League | r: Refresh", classes="tab-hint")
        with VerticalScroll(classes="standings-scroll", id="standings-scroll"):
            yield Label("Loading standings...", classes="loading")
        yield Footer()

    def on_mount(self) -> None:
        """Load standings data."""
        self.run_worker(self._fetch_standings())

    async def _fetch_standings(self) -> None:
        """Fetch standings from the API."""
        try:
            from tipoff.api import nba_stats

            self._standings_data = await nba_stats.get_standings()
            self._render_standings()
        except Exception:
            # Fall back to ESPN standings
            try:
                data = await self.client.get_standings()
                self._standings_data = []
                self._render_espn_standings(data)
            except Exception as e:
                self.notify(f"Error loading standings: {e}", severity="error")

    def _render_standings(self) -> None:
        """Render standings from nba_stats data."""
        scroll = self.query_one("#standings-scroll", VerticalScroll)
        scroll.remove_children()

        if not self._standings_data:
            scroll.mount(Label("No standings data available", classes="loading"))
            return

        if self._current_tab == "conference":
            self._render_conference()
        elif self._current_tab == "playoff_race":
            self._render_playoff_race()
        else:
            self._render_league()

    def _render_conference(self) -> None:
        """Render conference standings (East and West side by side)."""
        scroll = self.query_one("#standings-scroll", VerticalScroll)

        east_teams = [e for e in self._standings_data if e.team.conference == "Eastern"]
        west_teams = [e for e in self._standings_data if e.team.conference == "Western"]

        for label, teams in [("Eastern Conference", east_teams), ("Western Conference", west_teams)]:
            scroll.mount(Static(f"── {label} ──", classes="conference-label"))
            table = DataTable(id=f"standings-{label.split()[0].lower()}")
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns("#", "Team", "W", "L", "PCT", "GB", "STRK", "CLINCH")
            for entry in sorted(teams, key=lambda e: e.playoff_seed or 99):
                table.add_row(
                    str(entry.playoff_seed),
                    entry.team.abbreviation,
                    str(entry.wins),
                    str(entry.losses),
                    f"{entry.pct:.3f}",
                    entry.games_behind,
                    entry.streak,
                    entry.clinched,
                )
            scroll.mount(table)

    def _render_playoff_race(self) -> None:
        """Render playoff race view with seeds, play-in, and bubble teams."""
        scroll = self.query_one("#standings-scroll", VerticalScroll)

        for conf_name in ("Eastern", "Western"):
            teams = [e for e in self._standings_data if e.team.conference == conf_name]
            teams.sort(key=lambda e: e.playoff_seed or 99)

            scroll.mount(Static(f"── {conf_name} Conference ──", classes="conference-label"))

            table = DataTable()
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns("#", "Team", "W", "L", "PCT", "GB", "Zone")

            for entry in teams:
                seed = entry.playall_seed or 0
                if seed <= 6:
                    zone = "PLAYOFF"
                elif seed <= 10:
                    zone = "PLAY-IN"
                else:
                    zone = "LOTTERY"

                table.add_row(
                    str(seed),
                    entry.team.abbreviation,
                    str(entry.wins),
                    str(entry.losses),
                    f"{entry.pct:.3f}",
                    entry.games_behind,
                    zone,
                )
            scroll.mount(table)

    def _render_league(self) -> None:
        """Render all teams sorted by winning percentage."""
        scroll = self.query_one("#standings-scroll", VerticalScroll)

        all_teams = sorted(self._standings_data, key=lambda e: e.pct, reverse=True)

        table = DataTable(id="standings-league")
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("#", "Team", "Conf", "W", "L", "PCT", "GB", "STRK")

        for i, entry in enumerate(all_teams, 1):
            table.add_row(
                str(i),
                entry.team.abbreviation,
                entry.team.conference[:1],
                str(entry.wins),
                str(entry.losses),
                f"{entry.pct:.3f}",
                entry.games_behind,
                entry.streak,
            )
        scroll.mount(table)

    def _render_espn_standings(self, data: dict) -> None:
        """Fallback: render standings from ESPN data."""
        scroll = self.query_one("#standings-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(Label("Standings data not available", classes="loading"))

    def action_show_conference(self) -> None:
        """Show conference tab."""
        self._current_tab = "conference"
        self._render_standings()

    def action_show_playoff_race(self) -> None:
        """Show playoff race tab."""
        self._current_tab = "playoff_race"
        self._render_standings()

    def action_show_league(self) -> None:
        """Show league tab."""
        self._current_tab = "league"
        self._render_standings()

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Manually refresh standings."""
        self.client.clear_cache()
        self.run_worker(self._fetch_standings())
        self.notify("Refreshed")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
