"""Shared utilities for chess game analysis modules."""

import chess

# Canonical color-string to chess.Color mapping
COLOR_MAP = {"white": chess.WHITE, "black": chess.BLACK}

# Result strings that count as a loss
_LOSS_RESULTS = frozenset({"checkmated", "timeout", "resigned", "abandoned", "lose"})


def game_result(game) -> str:
    """Normalize a ChessGame result to 'win', 'loss', or 'draw'.

    Works with any object that has .white_result, .black_result, .my_color.
    """
    raw = (game.white_result if game.my_color == "white"
           else game.black_result).lower()
    if raw == "win":
        return "win"
    if raw in _LOSS_RESULTS:
        return "loss"
    return "draw"
