"""Data models for normalizing NBA API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NBATeam:
    """Normalized NBA team."""

    id: str
    abbreviation: str
    name: str
    city: str
    conference: str = ""  # "Eastern" or "Western"
    division: str = ""
    color: str = ""
    logo_url: str = ""
    seed: int | None = None
    wins: int = 0
    losses: int = 0


@dataclass
class NBAGame:
    """Normalized NBA game."""

    id: str
    date: str  # ISO format date string
    status: str  # FUT, LIVE, FINAL, PPD, CNCL, HALFTIME
    away_team: NBATeam
    home_team: NBATeam
    away_score: int = 0
    home_score: int = 0
    period: int = 0  # Current period (1-4 for quarters, 5+ for OT)
    clock: str = ""  # e.g. "8:45"
    away_quarter_scores: list[int] = field(default_factory=list)
    home_quarter_scores: list[int] = field(default_factory=list)
    series: NBASeries | None = None
    broadcasts: list[str] = field(default_factory=list)
    venue: str = ""


@dataclass
class NBASeries:
    """NBA playoff series."""

    id: str
    round_num: int  # 1=First Round, 2=Conf Semis, 3=Conf Finals, 4=NBA Finals
    conference: str  # "Eastern", "Western", or "" for NBA Finals
    higher_seed: NBATeam
    lower_seed: NBATeam
    higher_seed_wins: int = 0
    lower_seed_wins: int = 0
    total_games: int = 7
    completed: bool = False
    summary: str = ""  # e.g. "BOS leads 3-2"


@dataclass
class NBAStandingsEntry:
    """A single team's standings data."""

    team: NBATeam
    wins: int = 0
    losses: int = 0
    pct: float = 0.0
    games_behind: str = "-"  # "-" for division leader
    streak: str = ""  # e.g. "W4" or "L2"
    home_record: str = ""
    road_record: str = ""
    last_10: str = ""
    playoff_seed: int = 0
    clinched: str = ""  # "x" for playoff berth, "z" for top seed, etc.


@dataclass
class NBAPlayer:
    """Normalized NBA player."""

    id: str
    name: str
    position: str  # PG, SG, SF, PF, C
    number: int | None = None
    team: NBATeam | None = None
    height: str = ""
    weight: str = ""
    age: int = 0
    experience: str = ""


@dataclass
class NBABoxScoreEntry:
    """A single player's box score line."""

    player_id: str
    player_name: str
    minutes: str = ""
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    three_pointers_made: int = 0
    three_pointers_attempted: int = 0
    free_throws_made: int = 0
    free_throws_attempted: int = 0
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    personal_fouls: int = 0
    points: int = 0
    plus_minus: int = 0
    starter: bool = True


@dataclass
class NBAPlayByPlayEvent:
    """A single play-by-play event."""

    event_num: int
    period: int
    clock: str
    event_type: str  # "made_shot", "missed_shot", "free_throw", "rebound", "turnover", "foul", "timeout", "substitution", "period_end"
    description: str = ""
    team: str = ""  # Team abbreviation
    player_name: str = ""
    home_score: int = 0
    away_score: int = 0


@dataclass
class NBAStatsLeader:
    """A stats leader entry."""

    rank: int
    player_id: str
    player_name: str
    team_abbreviation: str
    value: str  # Formatted stat value
    stat_category: str = ""


# --- ESPN API normalization helpers ---


def normalize_espn_team(team_data: dict[str, Any]) -> NBATeam:
    """Normalize an ESPN team object into NBATeam."""
    return NBATeam(
        id=str(team_data.get("id", "")),
        abbreviation=team_data.get("abbreviation", ""),
        name=team_data.get("displayName", ""),
        city=team_data.get("location", ""),
        color=team_data.get("color", ""),
        logo_url=team_data.get("logo", ""),
    )


def normalize_espn_game(event: dict[str, Any]) -> NBAGame:
    """Normalize an ESPN scoreboard event into NBAGame."""
    competition = event.get("competitions", [{}])[0]
    status = event.get("status", {})
    status_type = status.get("type", {})

    # Map ESPN status to internal state
    state = status_type.get("state", "")
    name = status_type.get("name", "")
    game_state = _map_espn_state(state, name)

    # Extract teams
    competitors = competition.get("competitors", [])
    home_data = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away_data = next((c for c in competitors if c.get("homeAway") == "away"), {})

    home_team = normalize_espn_team(home_data.get("team", {}))
    away_team = normalize_espn_team(away_data.get("team", {}))

    # Update wins/losses from records
    if home_records := home_data.get("records", []):
        home_summary = home_records[0].get("summary", "")
        if "-" in home_summary:
            parts = home_summary.split("-")
            home_team.wins = int(parts[0])
            home_team.losses = int(parts[1].split(" ")[0])

    if away_records := away_data.get("records", []):
        away_summary = away_records[0].get("summary", "")
        if "-" in away_summary:
            parts = away_summary.split("-")
            away_team.wins = int(parts[0])
            away_team.losses = int(parts[1].split(" ")[0])

    home_score = int(home_data.get("score", 0))
    away_score = int(away_data.get("score", 0))

    # Extract period and clock
    situation = competition.get("situation", {})
    period = situation.get("period", 0)
    clock = situation.get("clock", "")

    # Quarter-by-quarter scores
    home_quarter_scores = [int(ls.get("value", 0)) for ls in home_data.get("linescores", [])]
    away_quarter_scores = [int(ls.get("value", 0)) for ls in away_data.get("linescores", [])]

    # Extract series info (playoffs)
    series_data = competition.get("series", {})
    series = None
    if series_data:
        series_competitors = series_data.get("competitors", [])
        higher_seed = away_team
        lower_seed = home_team
        higher_seed_wins = 0
        lower_seed_wins = 0

        # Determine which team is higher seed
        for sc in series_competitors:
            seed = sc.get("seed", 99)
            if seed is not None:
                wins = int(sc.get("wins", 0))
                team_id = str(sc.get("id", ""))
                if team_id == away_team.id and seed == 1:
                    higher_seed = away_team
                    lower_seed = home_team
                    higher_seed_wins = wins
                elif team_id == home_team.id and seed == 1:
                    higher_seed = home_team
                    lower_seed = away_team
                    higher_seed_wins = wins

        series = NBASeries(
            id=str(series_data.get("id", "")),
            round_num=0,  # Determined from bracket context
            conference="",
            higher_seed=higher_seed,
            lower_seed=lower_seed,
            higher_seed_wins=higher_seed_wins,
            lower_seed_wins=lower_seed_wins,
            total_games=int(series_data.get("totalCompetitions", 7)),
            completed=bool(series_data.get("completed", False)),
            summary=series_data.get("summary", ""),
        )

    # Broadcasts
    broadcasts = []
    for b in competition.get("broadcasts", []):
        if name := b.get("names", []):
            broadcasts.extend(name)

    # Venue
    venue = competition.get("venue", {}).get("fullName", "")

    return NBAGame(
        id=str(event.get("id", "")),
        date=event.get("date", ""),
        status=game_state,
        away_team=away_team,
        home_team=home_team,
        away_score=away_score,
        home_score=home_score,
        period=period,
        clock=clock,
        away_quarter_scores=away_quarter_scores,
        home_quarter_scores=home_quarter_scores,
        series=series,
        broadcasts=broadcasts,
        venue=venue,
    )


def _map_espn_state(state: str, name: str) -> str:
    """Map ESPN game state to internal state string."""
    if state == "pre":
        return "FUT"
    if state == "in":
        if name == "STATUS_HALFTIME" or "halftime" in name.lower():
            return "HALFTIME"
        return "LIVE"
    if state == "post":
        if "postponed" in name.lower():
            return "PPD"
        if "canceled" in name.lower():
            return "CNCL"
        return "FINAL"
    if "suspended" in name.lower():
        return "LIVE"
    return "FUT"


def format_period(period: int) -> str:
    """Format a period number into a display string."""
    if period <= 0:
        return ""
    if period == 1:
        return "1st Quarter"
    if period == 2:
        return "2nd Quarter"
    if period == 3:
        return "3rd Quarter"
    if period == 4:
        return "4th Quarter"
    if period == 5:
        return "OT"
    return f"{period - 4}OT"


def format_period_short(period: int) -> str:
    """Format a period number into a short display string."""
    if period <= 0:
        return ""
    if period <= 4:
        return f"Q{period}"
    if period == 5:
        return "OT"
    return f"{period - 4}OT"
