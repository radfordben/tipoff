"""ESPN API async client for NBA data."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from tipoff.api.models import NBAGame, NBATeam, normalize_espn_game, normalize_espn_team

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
DEFAULT_CACHE_TTL = 30.0
LIVE_CACHE_TTL = 10.0


class NBAClient:
    """Async HTTP client for NBA data via ESPN API."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "Tipoff/1.0"},
            follow_redirects=True,
        )
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = DEFAULT_CACHE_TTL

    async def _get(self, endpoint: str, cache_ttl: float | None = None) -> dict[str, Any]:
        """Fetch data from ESPN API with caching."""
        url = f"{BASE_URL}/{endpoint}"
        ttl = cache_ttl or self._cache_ttl
        now = asyncio.get_event_loop().time()

        if url in self._cache:
            ts, data = self._cache[url]
            if now - ts < ttl:
                return data

        response = await self._http.get(url)
        response.raise_for_status()
        data = response.json()
        self._cache[url] = (now, data)
        return data

    async def get_scoreboard(self, date: str | None = None) -> list[NBAGame]:
        """Fetch games for a date (YYYYMMDD format) or today.

        Returns a list of NBAGame objects normalized from ESPN events.
        """
        endpoint = "scoreboard"
        if date:
            endpoint = f"scoreboard?dates={date}"

        data = await self._get(endpoint, cache_ttl=LIVE_CACHE_TTL)
        events = data.get("events", [])
        return [normalize_espn_game(event) for event in events]

    async def get_teams(self) -> list[NBATeam]:
        """Fetch all NBA teams."""
        data = await self._get("teams")
        teams_data = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        return [normalize_espn_team(t.get("team", {})) for t in teams_data]

    async def get_game_summary(self, event_id: str) -> dict[str, Any]:
        """Fetch game summary (box score, play-by-play, etc.)."""
        return await self._get(f"summary?event={event_id}", cache_ttl=LIVE_CACHE_TTL)

    async def get_team_schedule(self, team_id: str, season: int | None = None) -> dict[str, Any]:
        """Fetch a team's schedule."""
        endpoint = f"teams/{team_id}/schedule"
        if season:
            endpoint += f"?season={season}"
        return await self._get(endpoint)

    async def get_standings(self) -> dict[str, Any]:
        """Fetch NBA standings."""
        return await self._get("standings")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()

    @staticmethod
    def get_nba_today() -> str:
        """Get today's date in ET (NBA uses Eastern Time)."""
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        return datetime.now(et).strftime("%Y%m%d")
