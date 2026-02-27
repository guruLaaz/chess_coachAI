"""Tests for LichessFetcher."""

import json
import re
import pytest
from aioresponses import aioresponses
from lichess_fetcher import LichessFetcher, LICHESS_API_BASE


USERNAME = "TestPlayer"
GAMES_URL = f"{LICHESS_API_BASE}/games/user/{USERNAME}"
GAMES_URL_PATTERN = re.compile(rf"^{re.escape(GAMES_URL)}")


def _ndjson_payload(games):
    """Create an NDJSON byte payload from a list of dicts."""
    return "\n".join(json.dumps(g) for g in games).encode()


def _make_lichess_game(game_id="abc1", speed="blitz"):
    return {
        "id": game_id,
        "speed": speed,
        "status": "resign",
        "players": {
            "white": {"user": {"name": "TestPlayer"}},
            "black": {"user": {"name": "Opponent"}},
        },
        "winner": "white",
        "lastMoveAt": 1700000000000,
        "pgn": '[Event "Rated Blitz"]\n\n1. e4 e5 1-0',
        "opening": {"eco": "C20", "name": "King Pawn Opening"},
    }


class TestFetchGames:
    @pytest.mark.asyncio
    async def test_fetches_games_successfully(self):
        games_data = [_make_lichess_game("abc1"), _make_lichess_game("abc2")]
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, body=_ndjson_payload(games_data),
                     content_type="application/x-ndjson")
            fetcher = LichessFetcher()
            games = await fetcher.fetch_games(USERNAME)
        assert len(games) == 2
        assert games[0]["id"] == "abc1"
        assert games[1]["id"] == "abc2"

    @pytest.mark.asyncio
    async def test_empty_response(self):
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, body=b"",
                     content_type="application/x-ndjson")
            fetcher = LichessFetcher()
            games = await fetcher.fetch_games(USERNAME)
        assert games == []

    @pytest.mark.asyncio
    async def test_single_game(self):
        games_data = [_make_lichess_game()]
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, body=_ndjson_payload(games_data),
                     content_type="application/x-ndjson")
            fetcher = LichessFetcher()
            games = await fetcher.fetch_games(USERNAME)
        assert len(games) == 1
        assert games[0]["opening"]["eco"] == "C20"

    @pytest.mark.asyncio
    async def test_404_raises(self):
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, status=404)
            fetcher = LichessFetcher()
            with pytest.raises(Exception):
                await fetcher.fetch_games(USERNAME)

    @pytest.mark.asyncio
    async def test_since_param_passed(self):
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, body=b"",
                     content_type="application/x-ndjson")
            fetcher = LichessFetcher()
            await fetcher.fetch_games(USERNAME, since=1000000)
            assert mock.requests

    @pytest.mark.asyncio
    async def test_blank_lines_in_ndjson_skipped(self):
        """Blank lines between NDJSON entries are ignored."""
        game = _make_lichess_game("abc1")
        payload = b"\n" + json.dumps(game).encode() + b"\n\n"
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, body=payload,
                     content_type="application/x-ndjson")
            fetcher = LichessFetcher()
            games = await fetcher.fetch_games(USERNAME)
        assert len(games) == 1
        assert games[0]["id"] == "abc1"

    @pytest.mark.asyncio
    async def test_500_server_error_raises(self):
        """HTTP 500 raises an exception (not just 404)."""
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, status=500)
            fetcher = LichessFetcher()
            with pytest.raises(Exception):
                await fetcher.fetch_games(USERNAME)

    @pytest.mark.asyncio
    async def test_429_rate_limit_raises(self):
        """HTTP 429 (rate limited) raises an exception."""
        with aioresponses() as mock:
            mock.get(GAMES_URL_PATTERN, status=429)
            fetcher = LichessFetcher()
            with pytest.raises(Exception):
                await fetcher.fetch_games(USERNAME)
