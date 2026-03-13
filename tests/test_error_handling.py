"""Tests for crash resilience — verify that errors are caught gracefully."""

import json
import re
import chess
import chess.engine
import pytest
from unittest.mock import patch, MagicMock
from aioresponses import aioresponses

from pgn_parser import PGNParser
from chessgame import ChessGame
from stockfish_evaluator import StockfishEvaluator
from endgame_detector import EndgameClassifier
from chesscom_fetcher import ChessCom_Fetcher, BASE_URL
from lichess_fetcher import LichessFetcher, LICHESS_API_BASE


# ---------------------------------------------------------------------------
# PGN Parser — read_game exceptions
# ---------------------------------------------------------------------------

class TestPGNParserErrorHandling:
    def test_parse_moves_exception_returns_none(self):
        with patch("pgn_parser.chess.pgn.read_game", side_effect=Exception("corrupt")):
            assert PGNParser.parse_moves("1. e4 e5") is None

    def test_parse_moves_with_clocks_exception_returns_none(self):
        with patch("pgn_parser.chess.pgn.read_game", side_effect=Exception("corrupt")):
            assert PGNParser.parse_moves_with_clocks("1. e4 e5") is None

    def test_replay_to_position_exception_returns_none(self):
        with patch("pgn_parser.chess.pgn.read_game", side_effect=Exception("corrupt")):
            assert PGNParser.replay_to_position("1. e4 e5", 0) is None


# ---------------------------------------------------------------------------
# ChessGame — bad timestamps
# ---------------------------------------------------------------------------

def _chesscom_game_data(**overrides):
    """Minimal valid Chess.com game JSON."""
    data = {
        "white": {"username": "testuser", "result": "win"},
        "black": {"username": "opponent", "result": "lose"},
        "end_time": 1700000000,
        "time_class": "blitz",
        "url": "https://chess.com/game/123",
        "rules": "chess",
    }
    data.update(overrides)
    return data


def _lichess_game_data(**overrides):
    """Minimal valid Lichess game JSON."""
    data = {
        "id": "abc123",
        "speed": "blitz",
        "status": "resign",
        "variant": "standard",
        "players": {
            "white": {"user": {"name": "testuser"}},
            "black": {"user": {"name": "opponent"}},
        },
        "winner": "white",
        "lastMoveAt": 1700000000000,
    }
    data.update(overrides)
    return data


class TestChessGameErrorHandling:
    def test_from_json_bad_timestamp(self):
        data = _chesscom_game_data(end_time=-99999999999999)
        game = ChessGame.from_json(data, "testuser")
        assert game is not None
        assert game.end_time is not None

    def test_from_json_overflow_timestamp(self):
        data = _chesscom_game_data(end_time=99999999999999)
        game = ChessGame.from_json(data, "testuser")
        assert game is not None

    def test_from_lichess_json_bad_timestamp(self):
        data = _lichess_game_data(lastMoveAt=-99999999999999999)
        game = ChessGame.from_lichess_json(data, "testuser")
        assert game is not None
        assert game.end_time is not None


# ---------------------------------------------------------------------------
# Stockfish Evaluator — engine crash types
# ---------------------------------------------------------------------------

class TestStockfishErrorHandling:
    def _make_evaluator(self):
        evaluator = StockfishEvaluator("dummy_path", depth=18)
        evaluator._engine = MagicMock()
        return evaluator

    def test_evaluate_engine_error_returns_none(self):
        evaluator = self._make_evaluator()
        evaluator._engine.analyse.side_effect = chess.engine.EngineError("bad move")
        assert evaluator.evaluate(chess.Board()) is None

    def test_evaluate_broken_pipe_returns_none(self):
        evaluator = self._make_evaluator()
        evaluator._engine.analyse.side_effect = BrokenPipeError("pipe gone")
        assert evaluator.evaluate(chess.Board()) is None

    def test_evaluate_timeout_returns_none(self):
        evaluator = self._make_evaluator()
        evaluator._engine.analyse.side_effect = TimeoutError("too slow")
        assert evaluator.evaluate(chess.Board()) is None

    def test_evaluate_os_error_returns_none(self):
        evaluator = self._make_evaluator()
        evaluator._engine.analyse.side_effect = OSError("engine died")
        assert evaluator.evaluate(chess.Board()) is None


# ---------------------------------------------------------------------------
# Chess.com Fetcher — network errors
# ---------------------------------------------------------------------------

class TestChessComFetcherErrorHandling:
    @pytest.mark.asyncio
    async def test_get_archives_network_error(self):
        fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")
        with aioresponses() as mock:
            url = f"{BASE_URL}/testuser/games/archives"
            mock.get(url, exception=ConnectionError("network down"))
            result = await fetcher.get_archives("testuser")
            assert result == []

    @pytest.mark.asyncio
    async def test_get_archives_500_returns_empty(self):
        fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")
        with aioresponses() as mock:
            url = f"{BASE_URL}/testuser/games/archives"
            mock.get(url, status=500)
            result = await fetcher.get_archives("testuser")
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_games_by_month_network_error(self):
        fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")
        with aioresponses() as mock:
            url = f"{BASE_URL}/testuser/games/2025/01"
            mock.get(url, exception=ConnectionError("network down"))
            result = await fetcher.fetch_games_by_month(url)
            assert result == {"games": []}

    @pytest.mark.asyncio
    async def test_fetch_games_by_month_500_returns_empty(self):
        fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")
        with aioresponses() as mock:
            url = f"{BASE_URL}/testuser/games/2025/01"
            mock.get(url, status=500)
            result = await fetcher.fetch_games_by_month(url)
            assert result == {"games": []}


# ---------------------------------------------------------------------------
# Lichess Fetcher — network errors + bad NDJSON
# ---------------------------------------------------------------------------

LICHESS_GAMES_URL = f"{LICHESS_API_BASE}/games/user/TestPlayer"
LICHESS_URL_PATTERN = re.compile(rf"^{re.escape(LICHESS_GAMES_URL)}")


class TestLichessFetcherErrorHandling:
    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self):
        with aioresponses() as mock:
            mock.get(LICHESS_URL_PATTERN, exception=ConnectionError("network down"))
            fetcher = LichessFetcher()
            games = await fetcher.fetch_games("TestPlayer")
            assert games == []

    @pytest.mark.asyncio
    async def test_bad_ndjson_line_skipped(self):
        """One bad JSON line among valid ones — bad line skipped, valid ones kept."""
        valid_game = {"id": "abc1", "speed": "blitz"}
        payload = json.dumps(valid_game).encode() + b"\nNOT_JSON\n" + json.dumps({"id": "abc2"}).encode()
        with aioresponses() as mock:
            mock.get(LICHESS_URL_PATTERN, body=payload,
                     content_type="application/x-ndjson")
            fetcher = LichessFetcher()
            games = await fetcher.fetch_games("TestPlayer")
            assert len(games) == 2
            assert games[0]["id"] == "abc1"
            assert games[1]["id"] == "abc2"


# ---------------------------------------------------------------------------
# Endgame Detector — PGN parse exception in _replay_moves
# ---------------------------------------------------------------------------

class TestEndgameDetectorErrorHandling:
    def test_replay_moves_pgn_parse_exception(self):
        """If PGN parsing raises, _replay_moves yields nothing (no crash)."""
        game = MagicMock()
        game.pgn = "1. e4 e5"
        game.game_url = "https://example.com/game/1"

        with patch("endgame_detector.PGNParser.parse_moves_with_clocks",
                   side_effect=Exception("parse error")):
            results = list(EndgameClassifier._replay_moves(game))
            assert results == []

    def test_analyze_game_all_with_bad_pgn(self):
        """analyze_game_all returns empty results dict when PGN parsing fails."""
        game = MagicMock()
        game.pgn = "corrupted pgn data"
        game.game_url = "https://example.com/game/1"
        game.my_color = "white"

        with patch("endgame_detector.PGNParser.parse_moves_with_clocks",
                   side_effect=Exception("parse error")):
            results = EndgameClassifier.analyze_game_all(game)
            # All definitions should be None (no endgame detected)
            for defn in results.values():
                assert defn is None
