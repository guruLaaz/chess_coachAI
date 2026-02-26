# opening_detector.py

from dataclasses import dataclass, field
from typing import List, Optional

import chess
import chess.polyglot


@dataclass
class DeviationResult:
    """Result of finding where a game deviates from opening book theory."""
    deviation_ply: int          # 0-based ply where the first non-book move occurs
    deviating_side: str         # "white" or "black"
    board_at_deviation: chess.Board  # position right before the non-book move
    is_fully_booked: bool       # True if all moves were in the book
    played_move: Optional[chess.Move] = None          # the move actually played
    book_moves: List[chess.Move] = field(default_factory=list)  # all book moves at this position


class OpeningDetector:
    """Detects where a game deviates from a polyglot opening book."""

    def __init__(self, book_path):
        """Load a polyglot .bin opening book from the given path."""
        self.book_path = book_path

    def find_deviation(self, moves):
        """Find the first move that deviates from the opening book.

        Args:
            moves: List of chess.Move objects from a parsed game.

        Returns:
            DeviationResult, or None if moves is empty.
        """
        if not moves:
            return None

        board = chess.Board()
        last_booked_board = board.copy()

        with chess.polyglot.open_reader(self.book_path) as reader:
            for ply, move in enumerate(moves):
                book_entries = list(reader.find_all(board))
                book_moves = [entry.move for entry in book_entries]

                if move not in book_moves:
                    deviating_side = "white" if board.turn == chess.WHITE else "black"
                    return DeviationResult(
                        deviation_ply=ply,
                        deviating_side=deviating_side,
                        board_at_deviation=board.copy(),
                        is_fully_booked=False,
                        played_move=move,
                        book_moves=book_moves,
                    )

                last_booked_board = board.copy()
                board.push(move)

        # All moves were in the book
        return DeviationResult(
            deviation_ply=len(moves),
            deviating_side="none",
            board_at_deviation=last_booked_board,
            is_fully_booked=True,
        )
