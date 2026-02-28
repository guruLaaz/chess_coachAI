"""Endgame detection and classification from chess game PGNs."""

from dataclasses import dataclass
from typing import List, Optional

import chess

from pgn_parser import PGNParser


# Standard piece values (pawns)
_PIECE_VALUES = {
    chess.QUEEN: 9,
    chess.ROOK: 5,
    chess.BISHOP: 3,
    chess.KNIGHT: 3,
    chess.PAWN: 1,
}

# Result strings that count as a loss (same as RepertoireAnalyzer)
_LOSS_RESULTS = {"checkmated", "timeout", "resigned", "abandoned", "lose"}


@dataclass
class EndgameInfo:
    """Per-game endgame classification."""
    endgame_type: str          # "R vs R", "Pawn", "Q vs RR", etc.
    endgame_ply: int           # ply at which endgame was first detected
    material_balance: str      # "equal", "up", "down"
    my_result: str             # "win", "loss", "draw"


class EndgameClassifier:
    """Detects and classifies endgames from chess games."""

    @staticmethod
    def is_endgame(board):
        """Check if a position is an endgame.

        An endgame is reached when:
        - No queens remain on the board, OR
        - Each side that has a queen has at most 1 additional minor piece
        """
        w_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
        b_queens = len(board.pieces(chess.QUEEN, chess.BLACK))

        if w_queens == 0 and b_queens == 0:
            return True

        # If queens are present, check if each side with a queen has
        # at most 1 minor piece (bishop or knight) and no rooks
        for color, q_count in [(chess.WHITE, w_queens), (chess.BLACK, b_queens)]:
            if q_count > 0:
                rooks = len(board.pieces(chess.ROOK, color))
                minors = (len(board.pieces(chess.BISHOP, color))
                          + len(board.pieces(chess.KNIGHT, color)))
                if rooks > 0 or minors > 1:
                    return False

        return True

    @staticmethod
    def _pieces_label(board, color):
        """Generate a compact piece label for one side.

        Returns e.g. "R", "RR", "QB", "BN", "" (empty if only king+pawns).
        Order: Q, R, B, N.
        """
        parts = []
        for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
            count = len(board.pieces(piece_type, color))
            if count:
                symbol = chess.piece_symbol(piece_type).upper()
                parts.append(symbol * count)
        return "".join(parts)

    @staticmethod
    def _material_value(board, color):
        """Compute total material value for one side (excluding king)."""
        total = 0
        for piece_type, value in _PIECE_VALUES.items():
            total += len(board.pieces(piece_type, color)) * value
        return total

    @staticmethod
    def classify_position(board, my_color):
        """Classify an endgame position.

        Returns (endgame_type, material_balance).
        """
        color_map = {"white": chess.WHITE, "black": chess.BLACK}
        my_c = color_map[my_color]
        opp_c = not my_c

        my_label = EndgameClassifier._pieces_label(board, my_c)
        opp_label = EndgameClassifier._pieces_label(board, opp_c)

        # Endgame type
        if not my_label and not opp_label:
            endgame_type = "Pawn"
        elif my_label and opp_label:
            endgame_type = f"{my_label} vs {opp_label}"
        elif my_label:
            endgame_type = f"{my_label} vs -"
        else:
            endgame_type = f"- vs {opp_label}"

        # Material balance
        my_mat = EndgameClassifier._material_value(board, my_c)
        opp_mat = EndgameClassifier._material_value(board, opp_c)

        if my_mat > opp_mat:
            material_balance = "up"
        elif my_mat < opp_mat:
            material_balance = "down"
        else:
            material_balance = "equal"

        return endgame_type, material_balance

    @staticmethod
    def _game_result(game):
        """Map a ChessGame to 'win', 'loss', or 'draw'."""
        result = (game.white_result.lower() if game.my_color == "white"
                  else game.black_result.lower())
        if result == "win":
            return "win"
        if result in _LOSS_RESULTS:
            return "loss"
        return "draw"

    @classmethod
    def analyze_game(cls, game):
        """Analyze a single game for endgame classification.

        Returns EndgameInfo if the game reached an endgame, None otherwise.
        """
        if not game.pgn:
            return None

        moves = PGNParser.parse_moves(game.pgn)
        if not moves:
            return None

        board = chess.Board()
        for ply, move in enumerate(moves):
            board.push(move)
            if cls.is_endgame(board):
                endgame_type, material_balance = cls.classify_position(
                    board, game.my_color)
                return EndgameInfo(
                    endgame_type=endgame_type,
                    endgame_ply=ply,
                    material_balance=material_balance,
                    my_result=cls._game_result(game),
                )

        return None

    @classmethod
    def aggregate(cls, games):
        """Analyze all games and return grouped endgame statistics.

        Returns a list of dicts sorted by game count descending:
        [{"type": "R vs R", "balance": "equal", "total": 30,
          "wins": 14, "losses": 12, "draws": 4,
          "win_pct": 47, "loss_pct": 40, "draw_pct": 13}, ...]
        """
        counts = {}  # (type, balance) -> {"wins": n, "losses": n, "draws": n}

        for game in games:
            info = cls.analyze_game(game)
            if info is None:
                continue

            key = (info.endgame_type, info.material_balance)
            if key not in counts:
                counts[key] = {"wins": 0, "losses": 0, "draws": 0}

            if info.my_result == "win":
                counts[key]["wins"] += 1
            elif info.my_result == "loss":
                counts[key]["losses"] += 1
            else:
                counts[key]["draws"] += 1

        results = []
        for (eg_type, balance), c in counts.items():
            total = c["wins"] + c["losses"] + c["draws"]
            results.append({
                "type": eg_type,
                "balance": balance,
                "total": total,
                "wins": c["wins"],
                "losses": c["losses"],
                "draws": c["draws"],
                "win_pct": round(100 * c["wins"] / total) if total else 0,
                "loss_pct": round(100 * c["losses"] / total) if total else 0,
                "draw_pct": round(100 * c["draws"] / total) if total else 0,
            })

        results.sort(key=lambda x: x["total"], reverse=True)
        return results
