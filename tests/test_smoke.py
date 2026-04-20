"""Smoke tests for Tipoff."""

from tipoff import __version__
from tipoff.api import NBAClient
from tipoff.app import TipoffApp


def test_version_is_string():
    assert isinstance(__version__, str)
    assert __version__


def test_nba_client_uses_async_http():
    import httpx

    client = NBAClient()
    assert isinstance(client._http, httpx.AsyncClient)


def test_app_accepts_refresh_interval():
    app = TipoffApp(refresh_interval=15)
    assert app.refresh_interval == 15