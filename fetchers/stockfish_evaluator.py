# stockfish_evaluator.py

from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine


MATE_SCORE_CP = 10000  # centipawns used to represent mate


@dataclass
class EvalResult:
    """Result of a Stockfish position evaluation."""
    score_cp: int               # centipawns from white's perspective
    score_mate: Optional[int]   # mate in N (positive = white mates), or None
    depth: int
    best_move: Optional[chess.Move]

    def score_for_color(self, color):
        """Return the centipawn score from the given color's perspective.

        Args:
            color: "white" or "black"
        """
        sign = 1 if color == "white" else -1
        return self.score_cp * sign


class StockfishEvaluator:
    """Evaluates chess positions using a Stockfish engine."""

    def __init__(self, stockfish_path, depth=18):
        self.stockfish_path = stockfish_path
        self.depth = depth
        self._engine = None

    def __enter__(self):
        self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._engine:
            self._engine.quit()
            self._engine = None
        return False

    def evaluate(self, board):
        """Evaluate a board position and return an EvalResult.

        The engine must be started (use as context manager).
        """
        if self._engine is None:
            raise RuntimeError("Engine not started. Use StockfishEvaluator as a context manager.")

        info = self._engine.analyse(board, chess.engine.Limit(depth=self.depth))
        score = info["score"].white()

        if score.is_mate():
            mate_in = score.mate()
            score_cp = MATE_SCORE_CP if mate_in > 0 else -MATE_SCORE_CP
        else:
            score_cp = score.score()
            mate_in = None

        best_move = info.get("pv", [None])[0] if info.get("pv") else None

        return EvalResult(
            score_cp=score_cp,
            score_mate=mate_in,
            depth=info.get("depth", self.depth),
            best_move=best_move,
        )
