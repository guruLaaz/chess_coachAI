"""Tests for the Celery worker analyze_user task.

All external dependencies (Stockfish, HTTP APIs, PostgreSQL) are mocked.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from chessgame import ChessGame
from endgame_detector import EndgameInfo
from repertoire_analyzer import OpeningEvaluation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_game(url="https://chess.com/game/1", color="white",
               white="testuser", black="opponent",
               pgn="1. e4 e5 *", time_class="blitz"):
    """Build a minimal ChessGame for testing."""
    g = ChessGame.__new__(ChessGame)
    g.game_url = url
    g.white = white
    g.black = black
    g.my_color = color
    g.white_result = "win"
    g.black_result = "checkmated"
    g.pgn = pgn
    g.eco_code = "B00"
    g.eco_name = "King's Pawn"
    g.time_class = time_class
    g.end_time = datetime(2025, 6, 1, tzinfo=timezone.utc)
    g.my_clock_left = 60.0
    g.opponent_clock_left = 30.0
    return g


def _make_evaluation(game_url="https://chess.com/game/1"):
    """Build a minimal OpeningEvaluation."""
    return OpeningEvaluation(
        eco_code="B00", eco_name="King's Pawn", my_color="white",
        deviation_ply=4, deviating_side="white", eval_cp=30,
        is_fully_booked=False,
        fen_at_deviation="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        best_move_uci="d2d4", played_move_uci="g1f3",
        book_moves_uci=["d2d4", "f2f4"], eval_loss_cp=10,
        game_moves_uci=["e2e4", "e7e5"], game_url=game_url,
        my_result="win", time_class="blitz",
        opponent_name="opponent", end_time=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAnalyzeUser:
    """Tests for worker.tasks.analyze_user."""

    @patch("worker.tasks.dbq")
    @patch("worker.tasks.asyncio.run")
    def test_no_games_found(self, mock_arun, mock_dbq):
        """When no games are fetched, job completes with total_games=0."""
        mock_arun.return_value = []

        from worker.tasks import analyze_user
        result = analyze_user(42, chesscom_user="testuser")

        assert result["total_games"] == 0
        # Verify job was marked complete
        mock_dbq.update_job.assert_any_call(
            42, status="complete", progress_pct=100,
            total_games=0, message="No games found.")

    @patch("worker.tasks.StockfishEvaluator")
    @patch("worker.tasks.OpeningDetector")
    @patch("worker.tasks.RepertoireAnalyzer")
    @patch("worker.tasks.EndgameClassifier")
    @patch("worker.tasks.dbq")
    @patch("worker.tasks.asyncio.run")
    def test_full_pipeline(self, mock_arun, mock_dbq, mock_endgame_cls,
                           mock_rep_cls, mock_detector_cls, mock_sf_cls):
        """Full pipeline with one uncached game runs all phases."""
        game = _make_game()
        mock_arun.return_value = [game]

        # DB returns no cached data
        mock_dbq.get_endgames.return_value = {}
        mock_dbq.get_cached_evaluations.return_value = {}

        # Endgame classifier returns a result
        mock_endgame_cls.analyze_game_all.return_value = {
            "queens-off": EndgameInfo(
                endgame_type="Pawn", endgame_ply=40,
                material_balance="equal", my_result="win",
                fen_at_endgame="8/8/8/8/8/8/8/8 w - - 0 1",
                game_url=game.game_url, material_diff=0,
                my_clock=60.0, opp_clock=30.0,
            ),
        }

        # Stockfish evaluator as context manager
        mock_sf_instance = MagicMock()
        mock_sf_cls.return_value.__enter__ = MagicMock(return_value=mock_sf_instance)
        mock_sf_cls.return_value.__exit__ = MagicMock(return_value=False)

        # RepertoireAnalyzer returns stats and new evals
        ev = _make_evaluation(game.game_url)
        mock_rep_instance = MagicMock()
        mock_rep_instance.analyze_repertoire.return_value = (
            {},  # opening_stats
            [(game, ev)],  # new_evals
        )
        mock_rep_cls.return_value = mock_rep_instance

        from worker.tasks import analyze_user
        result = analyze_user(42, chesscom_user="testuser")

        assert result["total_games"] == 1
        assert result["job_id"] == 42

        # Verify endgame analysis ran
        mock_endgame_cls.analyze_game_all.assert_called_once_with(game)
        mock_dbq.save_endgames_batch.assert_called_once()

        # Verify opening analysis ran
        mock_rep_instance.analyze_repertoire.assert_called_once()

        # Verify evaluations were saved
        mock_dbq.save_evaluations_batch.assert_called_once()

        # Verify final status
        mock_dbq.update_job.assert_any_call(
            42, status="complete", progress_pct=100,
            message="Analysis complete: 1 games")

    @patch("worker.tasks.StockfishEvaluator")
    @patch("worker.tasks.OpeningDetector")
    @patch("worker.tasks.RepertoireAnalyzer")
    @patch("worker.tasks.EndgameClassifier")
    @patch("worker.tasks.dbq")
    @patch("worker.tasks.asyncio.run")
    def test_all_cached_skips_engine(self, mock_arun, mock_dbq,
                                     mock_endgame_cls, mock_rep_cls,
                                     mock_detector_cls, mock_sf_cls):
        """When all games are cached, Stockfish is never started."""
        game = _make_game()
        mock_arun.return_value = [game]

        # Endgames fully cached
        mock_dbq.get_endgames.return_value = {
            game.game_url: {"queens-off": None, "minor-or-queen": None, "material": None}
        }

        # Evaluations fully cached
        ev = _make_evaluation(game.game_url)
        mock_dbq.get_cached_evaluations.return_value = {game.game_url: ev}

        from worker.tasks import analyze_user
        result = analyze_user(42, chesscom_user="testuser")

        assert result["total_games"] == 1
        # Stockfish should never have been instantiated
        mock_sf_cls.assert_not_called()
        # No new evaluations to save
        mock_dbq.save_evaluations_batch.assert_not_called()
        # Endgame analysis should have been skipped (no uncached games)
        mock_endgame_cls.analyze_game_all.assert_not_called()

    @patch("worker.tasks.dbq")
    @patch("worker.tasks.asyncio.run")
    def test_fetch_error_sets_failed(self, mock_arun, mock_dbq):
        """If fetching raises, job status is set to 'failed'."""
        mock_arun.side_effect = RuntimeError("API timeout")

        from worker.tasks import analyze_user
        with pytest.raises(RuntimeError, match="API timeout"):
            analyze_user(42, chesscom_user="testuser")

        mock_dbq.update_job.assert_any_call(
            42, status="failed", error_message="API timeout")

    @patch("worker.tasks.StockfishEvaluator")
    @patch("worker.tasks.OpeningDetector")
    @patch("worker.tasks.RepertoireAnalyzer")
    @patch("worker.tasks.EndgameClassifier")
    @patch("worker.tasks.dbq")
    @patch("worker.tasks.asyncio.run")
    def test_progress_updates(self, mock_arun, mock_dbq, mock_endgame_cls,
                              mock_rep_cls, mock_detector_cls, mock_sf_cls):
        """Job progress is updated through each pipeline phase."""
        game = _make_game()
        mock_arun.return_value = [game]
        mock_dbq.get_endgames.return_value = {}
        mock_dbq.get_cached_evaluations.return_value = {}
        mock_endgame_cls.analyze_game_all.return_value = {}

        mock_sf_instance = MagicMock()
        mock_sf_cls.return_value.__enter__ = MagicMock(return_value=mock_sf_instance)
        mock_sf_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_rep_instance = MagicMock()
        mock_rep_instance.analyze_repertoire.return_value = ({}, [])
        mock_rep_cls.return_value = mock_rep_instance

        from worker.tasks import analyze_user
        analyze_user(42, chesscom_user="testuser")

        # Collect all status updates
        statuses = [
            call.kwargs.get("status") or call.args[1] if len(call.args) > 1 else call.kwargs.get("status")
            for call in mock_dbq.update_job.call_args_list
        ]
        # Filter out None (progress-only updates)
        statuses = [s for s in statuses if s]
        assert "fetching" in statuses
        assert "analyzing" in statuses
        assert "complete" in statuses

    @patch("worker.tasks.dbq")
    @patch("worker.tasks.asyncio.run")
    def test_lichess_only(self, mock_arun, mock_dbq):
        """Task works with only a Lichess username."""
        mock_arun.return_value = []

        from worker.tasks import analyze_user
        result = analyze_user(42, lichess_user="lichessplayer")

        assert result["total_games"] == 0
        mock_dbq.update_job.assert_any_call(
            42, status="complete", progress_pct=100,
            total_games=0, message="No games found.")


class TestFetchHelpers:
    """Tests for the async fetch helper functions."""

    @patch("worker.tasks.dbq")
    @patch("worker.tasks.ChessCom_Fetcher")
    def test_fetch_chesscom_uses_cache(self, mock_fetcher_cls, mock_dbq):
        """_fetch_chesscom_games uses DB cache for non-current months."""
        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher

        # Return two archive URLs
        async def get_archives(user):
            return ["https://api.chess.com/pub/player/test/games/2024/01",
                    "https://api.chess.com/pub/player/test/games/2024/02"]
        mock_fetcher.get_archives = get_archives

        # First archive is cached, second is not
        mock_dbq.get_archive.side_effect = [
            {"games": [{"url": "g1"}]},  # cached
            None,  # not cached
        ]

        async def fetch_month(url):
            return {"games": [{"url": "g2"}]}
        mock_fetcher.fetch_games_by_month = fetch_month

        # ChessGame.from_json returns None for our stub data (no valid fields)
        with patch("worker.tasks.ChessGame") as mock_cg:
            mock_cg.from_json.return_value = None
            from worker.tasks import _fetch_chesscom_games
            result = asyncio.run(_fetch_chesscom_games("test"))

        # Both archives were checked, but only second was fetched from API
        assert mock_dbq.get_archive.call_count == 2
        mock_dbq.save_archive.assert_called_once()  # only the uncached one

    def test_is_current_month(self):
        """_is_current_month correctly identifies current vs past months."""
        from worker.tasks import _is_current_month

        now = datetime.now(timezone.utc)
        current_url = f"https://api.chess.com/pub/player/x/games/{now.year}/{now.month:02d}"
        past_url = "https://api.chess.com/pub/player/x/games/2020/01"
        bad_url = "https://api.chess.com/pub/player/x/games"

        assert _is_current_month(current_url) is True
        assert _is_current_month(past_url) is False
        assert _is_current_month(bad_url) is True  # unparseable = treat as current
