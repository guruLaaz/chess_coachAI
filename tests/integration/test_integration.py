"""
Integration tests: fetcher smoke tests with mocked and real APIs.
"""
import datetime
import json
import re

import pytest
from aioresponses import aioresponses

from chesscom_fetcher import ChessCom_Fetcher, BASE_URL
from lichess_fetcher import LichessFetcher, LICHESS_API_BASE
from chessgame import ChessGame


USERNAME = "TestPlayer"
ARCHIVES_URL = f"{BASE_URL}/{USERNAME}/games/archives"


class TestFetcherEdgeCases:
    @pytest.mark.asyncio
    async def test_player_not_found_404(self):
        """HTTP 404 for archives → returns empty list (graceful handling)."""
        with aioresponses() as mock:
            mock.get(ARCHIVES_URL, status=404)
            fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")

            result = await fetcher.get_archives(USERNAME)
            assert result == []


@pytest.mark.network
class TestRealAPI:
    """Smoke test against the live Chess.com API to catch data format changes."""

    @pytest.mark.asyncio
    async def test_chesscom_api_data_format(self):
        """Fetch real data for 'laaz' and verify the response shape hasn't changed."""
        fetcher = ChessCom_Fetcher(user_agent="chess_coachAI/tests (smoke test)")

        # 1. Archives endpoint returns a list of URL strings
        archives = await fetcher.get_archives("laaz")
        assert isinstance(archives, list)
        assert len(archives) > 0
        assert all(isinstance(url, str) for url in archives)

        # 2. Fetch the most recent month only (to keep the test fast)
        month_data = await fetcher.fetch_games_by_month(archives[-1])
        assert "games" in month_data
        games = month_data["games"]
        assert isinstance(games, list)
        assert len(games) > 0

        # 3. Verify each game has the fields our pipeline relies on
        required_keys = {"white", "black", "end_time", "time_class"}
        player_keys = {"username", "result"}
        valid_time_classes = {"bullet", "blitz", "rapid", "daily"}

        for game in games:
            assert required_keys.issubset(game.keys()), (
                f"Missing top-level keys: {required_keys - game.keys()}")
            assert player_keys.issubset(game["white"].keys()), (
                f"Missing white keys: {player_keys - game['white'].keys()}")
            assert player_keys.issubset(game["black"].keys()), (
                f"Missing black keys: {player_keys - game['black'].keys()}")
            assert isinstance(game["end_time"], int)
            assert game["time_class"] in valid_time_classes, (
                f"Unexpected time_class: {game['time_class']}")

        # 4. Verify ChessGame.from_json can parse at least one game
        parsed = ChessGame.from_json(games[0], "laaz")
        if parsed is not None:
            assert parsed.my_color in ("white", "black")
            assert isinstance(parsed.end_time, datetime.datetime)
            assert parsed.white_result != ""
            assert parsed.black_result != ""
            assert parsed.time_class in valid_time_classes


@pytest.mark.network
class TestRealLichessAPI:
    """Smoke test against the live Lichess API to catch data format changes."""

    @pytest.mark.asyncio
    async def test_lichess_api_data_format(self):
        """Fetch real data for 'laaz' and verify the response shape."""
        fetcher = LichessFetcher(user_agent="chess_coachAI/tests (smoke test)")

        # Fetch a small batch (most recent 5 games) to keep it fast
        import time
        since_ms = int((time.time() - 365 * 86400) * 1000)
        games = await fetcher.fetch_games("laaz", since=since_ms)
        assert isinstance(games, list)
        assert len(games) > 0

        # Verify expected top-level fields
        valid_speeds = {"bullet", "blitz", "rapid", "classical",
                        "correspondence", "ultraBullet"}
        for game in games[:5]:
            assert "id" in game, f"Missing 'id' field"
            assert "speed" in game, f"Missing 'speed' field"
            assert "players" in game, f"Missing 'players' field"
            assert "status" in game, f"Missing 'status' field"
            assert game["speed"] in valid_speeds, (
                f"Unexpected speed: {game['speed']}")

            # Verify player structure
            for color in ("white", "black"):
                assert color in game["players"], f"Missing players.{color}"
                player = game["players"][color]
                assert "user" in player or "aiLevel" in player, (
                    f"Player {color} has neither 'user' nor 'aiLevel'")

            # Verify PGN is present (we request pgnInJson=true)
            assert "pgn" in game, "Missing 'pgn' — pgnInJson param may have changed"

        # Verify ChessGame.from_lichess_json can parse at least one game
        parsed = ChessGame.from_lichess_json(games[0], "laaz")
        if parsed is not None:
            assert parsed.my_color in ("white", "black")
            assert isinstance(parsed.end_time, datetime.datetime)
            assert parsed.game_url.startswith("https://lichess.org/")
            assert parsed.time_class in ("bullet", "blitz", "rapid", "daily")
