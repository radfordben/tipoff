"""Wrapper around nba_api for supplementary NBA statistics.

nba_api is synchronous and uses requests internally. This module wraps
its calls in asyncio.to_thread() to avoid blocking the Textual event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tipoff.api.models import NBABoxScoreEntry, NBAPlayer, NBAStandingsEntry, NBAStatsLeader

# Headers required by stats.nba.com to avoid 403 blocks
_NBA_HEADERS = {
    "Host": "stats.nba.com",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 30.0


def _get_cache(key: str) -> Any | None:
    """Get cached data if still valid."""
    import time

    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: Any) -> None:
    """Store data in cache."""
    import time

    _cache[key] = (time.time(), data)


async def get_standings(season: str = "2025-26") -> list[NBAStandingsEntry]:
    """Fetch NBA standings with playoff seeding and clinch indicators."""
    cache_key = f"standings_{season}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> list[NBAStandingsEntry]:
        from nba_api.stats.endpoints import leaguestandingsv3

        result = leaguestandingsv3.LeagueStandingsV3(
            league_id="00",
            season=season,
            season_type="Regular Season",
            headers=_NBA_HEADERS,
            timeout=60,
        )
        df = result.get_data_frames()[0]
        entries = []
        for _, row in df.iterrows():
            team = NBATeam(
                id=str(row.get("TeamID", "")),
                abbreviation=row.get("TeamAbr", ""),
                name=row.get("TeamCity", "") + " " + row.get("TeamName", ""),
                city=row.get("TeamCity", ""),
                conference=row.get("Conference", ""),
            )
            entry = NBAStandingsEntry(
                team=team,
                wins=int(row.get("WINS", 0)),
                losses=int(row.get("LOSSES", 0)),
                pct=float(row.get("PCT", 0)),
                games_behind=str(row.get("GB", "-")),
                streak=row.get("strCurrentStreak", ""),
                home_record=row.get("HOME_RECORD", ""),
                road_record=row.get("ROAD_RECORD", ""),
                last_10=row.get("L10", ""),
                playoff_seed=int(row.get("PlayoffRank", 0)),
                clinched=row.get("ClinchIndicator", ""),
            )
            entries.append(entry)
        return entries

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


async def get_box_score(game_id: str) -> dict[str, list[NBABoxScoreEntry]]:
    """Fetch player box scores for a game.

    Returns {"home": [...], "away": [...]}.
    """
    cache_key = f"boxscore_{game_id}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> dict[str, list[NBABoxScoreEntry]]:
        from nba_api.stats.endpoints import boxscoretraditionalv2

        result = boxscoretraditionalv2.BoxScoreTraditionalV2(
            game_id=game_id,
            headers=_NBA_HEADERS,
            timeout=60,
        )
        dfs = result.get_data_frames()
        # Player stats are in the first dataframe
        player_df = dfs[0] if len(dfs) > 0 else None

        home_players: list[NBABoxScoreEntry] = []
        away_players: list[NBABoxScoreEntry] = []

        if player_df is not None:
            for _, row in player_df.iterrows():
                entry = NBABoxScoreEntry(
                    player_id=str(row.get("PLAYER_ID", "")),
                    player_name=str(row.get("PLAYER_NAME", "")),
                    minutes=str(row.get("MIN", "")),
                    field_goals_made=int(row.get("FGM", 0) or 0),
                    field_goals_attempted=int(row.get("FGA", 0) or 0),
                    three_pointers_made=int(row.get("FG3M", 0) or 0),
                    three_pointers_attempted=int(row.get("FG3A", 0) or 0),
                    free_throws_made=int(row.get("FTM", 0) or 0),
                    free_throws_attempted=int(row.get("FTA", 0) or 0),
                    offensive_rebounds=int(row.get("OREB", 0) or 0),
                    defensive_rebounds=int(row.get("DREB", 0) or 0),
                    rebounds=int(row.get("REB", 0) or 0),
                    assists=int(row.get("AST", 0) or 0),
                    steals=int(row.get("STL", 0) or 0),
                    blocks=int(row.get("BLK", 0) or 0),
                    turnovers=int(row.get("TO", 0) or 0),
                    personal_fouls=int(row.get("PF", 0) or 0),
                    points=int(row.get("PTS", 0) or 0),
                    plus_minus=int(row.get("PLUS_MINUS", 0) or 0),
                    starter=str(row.get("START_POSITION", "")) != "",
                )
                if str(row.get("TEAM_ID", "")) == str(row.get("TEAM_CITY", "")):
                    home_players.append(entry)
                else:
                    away_players.append(entry)

        return {"home": home_players, "away": away_players}

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


async def get_play_by_play(game_id: str) -> list[dict[str, Any]]:
    """Fetch play-by-play data for a game."""
    cache_key = f"pbp_{game_id}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> list[dict[str, Any]]:
        from nba_api.stats.endpoints import playbyplayv2

        result = playbyplayv2.PlayByPlayV2(
            game_id=game_id,
            headers=_NBA_HEADERS,
            timeout=60,
        )
        df = result.get_data_frames()[0]
        plays = []
        for _, row in df.iterrows():
            event_type = _map_event_msg_type(int(row.get("EVENTMSGTYPE", 0)))
            plays.append(
                {
                    "event_num": int(row.get("EVENTNUM", 0)),
                    "period": int(row.get("PERIOD", 0)),
                    "clock": str(row.get("PCTIMESTRING", "")),
                    "event_type": event_type,
                    "description": str(row.get("HOMEDESCRIPTION", "") or row.get("VISITORDESCRIPTION", "") or ""),
                    "home_description": str(row.get("HOMEDESCRIPTION", "") or ""),
                    "away_description": str(row.get("VISITORDESCRIPTION", "") or ""),
                    "player_name": str(row.get("PLAYER_NAME", "") or ""),
                    "home_score": int(row.get("SCORE", "").split(" - ")[0]) if " - " in str(row.get("SCORE", "")) else 0,
                    "away_score": int(row.get("SCORE", "").split(" - ")[1]) if " - " in str(row.get("SCORE", "")) else 0,
                }
            )
        return plays

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


async def get_stats_leaders(category: str = "PTS", season_type: str = "Regular Season") -> list[NBAStatsLeader]:
    """Fetch league leaders for a stat category."""
    cache_key = f"leaders_{category}_{season_type}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> list[NBAStatsLeader]:
        from nba_api.stats.endpoints import leagueleaders

        result = leagueleaders.LeagueLeaders(
            league_id="00",
            per_mode="PerGame",
            stat_category=category,
            season_type=season_type,
            headers=_NBA_HEADERS,
            timeout=60,
        )
        df = result.get_data_frames()[0]
        leaders = []
        for rank, (_, row) in enumerate(df.iterrows(), 1):
            leaders.append(
                NBAStatsLeader(
                    rank=rank,
                    player_id=str(row.get("PLAYER_ID", "")),
                    player_name=str(row.get("PLAYER", "")),
                    team_abbreviation=str(row.get("TEAM", "")),
                    value=str(row.get(category, "")),
                    stat_category=category,
                )
            )
        return leaders[:20]  # Top 20

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


async def get_team_roster(team_id: str) -> list[NBAPlayer]:
    """Fetch a team's roster."""
    cache_key = f"roster_{team_id}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> list[NBAPlayer]:
        from nba_api.stats.endpoints import commonteamroster

        result = commonteamroster.CommonTeamRoster(
            team_id=team_id,
            headers=_NBA_HEADERS,
            timeout=60,
        )
        df = result.get_data_frames()[0]
        players = []
        for _, row in df.iterrows():
            players.append(
                NBAPlayer(
                    id=str(row.get("PLAYER_ID", "")),
                    name=str(row.get("PLAYER", "")),
                    position=str(row.get("POSITION", "")),
                    number=int(row.get("NUM", 0) or 0),
                    height=str(row.get("HEIGHT", "")),
                    weight=str(row.get("WEIGHT", "")),
                    age=int(row.get("AGE", 0) or 0),
                    experience=str(row.get("EXP", "")),
                )
            )
        return players

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


async def get_player_info(player_id: str) -> dict[str, Any]:
    """Fetch player info and career stats."""
    cache_key = f"player_{player_id}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> dict[str, Any]:
        from nba_api.stats.endpoints import commonplayerinfo

        result = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            headers=_NBA_HEADERS,
            timeout=60,
        )
        info_df = result.get_data_frames()[0]
        if len(info_df) == 0:
            return {}
        row = info_df.iloc[0]
        return {
            "id": str(row.get("PERSON_ID", "")),
            "name": str(row.get("DISPLAY_FIRST_LAST", "")),
            "team": str(row.get("TEAM_NAME", "")),
            "position": str(row.get("POSITION", "")),
            "number": str(row.get("JERSEY", "")),
            "height": str(row.get("HEIGHT", "")),
            "weight": str(row.get("WEIGHT", "")),
            "birthdate": str(row.get("BIRTHDATE", "")),
            "school": str(row.get("SCHOOL", "")),
            "country": str(row.get("COUNTRY", "")),
            "experience": str(row.get("SEASON_EXP", "")),
        }

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


async def get_player_game_log(player_id: str, season: str = "2025-26") -> list[dict[str, Any]]:
    """Fetch a player's game log."""
    cache_key = f"game_log_{player_id}_{season}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> list[dict[str, Any]]:
        from nba_api.stats.endpoints import playergamelog

        result = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            headers=_NBA_HEADERS,
            timeout=60,
        )
        df = result.get_data_frames()[0]
        games = []
        for _, row in df.iterrows():
            games.append(
                {
                    "date": str(row.get("GAME_DATE", "")),
                    "opponent": str(row.get("MATCHUP", "")),
                    "minutes": str(row.get("MIN", "")),
                    "points": int(row.get("PTS", 0) or 0),
                    "rebounds": int(row.get("REB", 0) or 0),
                    "assists": int(row.get("AST", 0) or 0),
                    "steals": int(row.get("STL", 0) or 0),
                    "blocks": int(row.get("BLK", 0) or 0),
                    "field_goals_made": int(row.get("FGM", 0) or 0),
                    "field_goals_attempted": int(row.get("FGA", 0) or 0),
                    "three_pointers_made": int(row.get("FG3M", 0) or 0),
                    "three_pointers_attempted": int(row.get("FG3A", 0) or 0),
                    "free_throws_made": int(row.get("FTM", 0) or 0),
                    "free_throws_attempted": int(row.get("FTA", 0) or 0),
                    "turnovers": int(row.get("TOV", 0) or 0),
                    "plus_minus": int(row.get("PLUS_MINUS", 0) or 0),
                }
            )
        return games

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


async def get_playoff_series(season: str = "2025-26") -> list[dict[str, Any]]:
    """Fetch playoff series information."""
    cache_key = f"playoff_series_{season}"
    if cached := _get_cache(cache_key):
        return cached

    def _fetch() -> list[dict[str, Any]]:
        from nba_api.stats.endpoints import commonplayoffseries

        result = commonplayoffseries.CommonPlayoffSeries(
            league_id="00",
            season=season,
            headers=_NBA_HEADERS,
            timeout=60,
        )
        df = result.get_data_frames()[0]
        series_list = []
        for _, row in df.iterrows():
            series_list.append(
                {
                    "game_id": str(row.get("GAME_ID", "")),
                    "home_team_id": str(row.get("HOME_TEAM_ID", "")),
                    "visitor_team_id": str(row.get("VISITOR_TEAM_ID", "")),
                    "series_id": str(row.get("SERIES_ID", "")),
                    "game_number": int(row.get("GAME_NUM", 0) or 0),
                }
            )
        return series_list

    data = await asyncio.to_thread(_fetch)
    _set_cache(cache_key, data)
    return data


def _map_event_msg_type(msg_type: int) -> str:
    """Map NBA EVENTMSGTYPE codes to internal event types."""
    mapping = {
        1: "made_shot",
        2: "missed_shot",
        3: "free_throw",
        4: "rebound",
        5: "turnover",
        6: "foul",
        7: "violation",
        8: "substitution",
        9: "timeout",
        10: "period_end",
        12: "start_period",
        13: "end_period",
    }
    return mapping.get(msg_type, "unknown")


def clear_cache() -> None:
    """Clear all cached nba_stats data."""
    _cache.clear()