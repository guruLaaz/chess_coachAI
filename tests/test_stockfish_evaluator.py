import chess
import chess.engine
from unittest.mock import patch, MagicMock

import pytest

from stockfish_evaluator import StockfishEvaluator, EvalResult, MATE_SCORE_CP


def _make_score(cp=None, mate=None):
    """Create a mock chess.engine score from white's perspective."""
    score = MagicMock()
    white_pov = MagicMock()

    if mate is not None:
        white_pov.is_mate.return_value = True
        white_pov.mate.return_value = mate
        white_pov.score.return_value = None
    else:
        white_pov.is_mate.return_value = False
        white_pov.mate.return_value = None
        white_pov.score.return_value = cp

    score.white.return_value = white_pov
    return score


class TestEvalResult:
    def test_score_for_white(self):
        result = EvalResult(score_cp=50, score_mate=None, depth=18, best_move=None)
        assert result.score_for_color("white") == 50

    def test_score_for_black(self):
        result = EvalResult(score_cp=50, score_mate=None, depth=18, best_move=None)
        assert result.score_for_color("black") == -50

    def test_negative_score_for_white(self):
        result = EvalResult(score_cp=-120, score_mate=None, depth=18, best_move=None)
        assert result.score_for_color("white") == -120

    def test_negative_score_for_black(self):
        result = EvalResult(score_cp=-120, score_mate=None, depth=18, best_move=None)
        assert result.score_for_color("black") == 120

    def test_zero_score(self):
        result = EvalResult(score_cp=0, score_mate=None, depth=18, best_move=None)
        assert result.score_for_color("white") == 0
        assert result.score_for_color("black") == 0

    def test_mate_score_for_color(self):
        result = EvalResult(score_cp=MATE_SCORE_CP, score_mate=3, depth=18, best_move=None)
        assert result.score_for_color("white") == MATE_SCORE_CP
        assert result.score_for_color("black") == -MATE_SCORE_CP


class TestStockfishEvaluator:
    def test_evaluate_returns_centipawn_score(self):
        mock_engine = MagicMock()
        mock_engine.analyse.return_value = {
            "score": _make_score(cp=35),
            "depth": 18,
            "pv": [chess.Move.from_uci("e2e4")],
        }

        evaluator = StockfishEvaluator("dummy_path", depth=18)
        evaluator._engine = mock_engine

        board = chess.Board()
        result = evaluator.evaluate(board)

        assert result.score_cp == 35
        assert result.score_mate is None
        assert result.depth == 18
        assert result.best_move == chess.Move.from_uci("e2e4")

    def test_evaluate_mate_score(self):
        mock_engine = MagicMock()
        mock_engine.analyse.return_value = {
            "score": _make_score(mate=3),
            "depth": 18,
            "pv": [chess.Move.from_uci("d1h5")],
        }

        evaluator = StockfishEvaluator("dummy_path", depth=18)
        evaluator._engine = mock_engine

        result = evaluator.evaluate(chess.Board())
        assert result.score_cp == MATE_SCORE_CP
        assert result.score_mate == 3

    def test_evaluate_negative_mate(self):
        mock_engine = MagicMock()
        mock_engine.analyse.return_value = {
            "score": _make_score(mate=-2),
            "depth": 18,
            "pv": [],
        }

        evaluator = StockfishEvaluator("dummy_path", depth=18)
        evaluator._engine = mock_engine

        result = evaluator.evaluate(chess.Board())
        assert result.score_cp == -MATE_SCORE_CP
        assert result.score_mate == -2

    def test_evaluate_no_pv(self):
        mock_engine = MagicMock()
        mock_engine.analyse.return_value = {
            "score": _make_score(cp=0),
            "depth": 18,
        }

        evaluator = StockfishEvaluator("dummy_path", depth=18)
        evaluator._engine = mock_engine

        result = evaluator.evaluate(chess.Board())
        assert result.best_move is None

    def test_evaluate_without_context_manager_raises(self):
        evaluator = StockfishEvaluator("dummy_path")
        with pytest.raises(RuntimeError, match="Engine not started"):
            evaluator.evaluate(chess.Board())

    @patch("stockfish_evaluator.chess.engine.SimpleEngine.popen_uci")
    def test_context_manager_starts_and_stops_engine(self, mock_popen):
        mock_engine = MagicMock()
        mock_popen.return_value = mock_engine

        with StockfishEvaluator("dummy_path") as evaluator:
            assert evaluator._engine is mock_engine

        mock_engine.quit.assert_called_once()

    @patch("stockfish_evaluator.chess.engine.SimpleEngine.popen_uci")
    def test_context_manager_cleans_up_on_exception(self, mock_popen):
        mock_engine = MagicMock()
        mock_popen.return_value = mock_engine

        with pytest.raises(ValueError):
            with StockfishEvaluator("dummy_path") as evaluator:
                raise ValueError("test error")

        mock_engine.quit.assert_called_once()
