"""Endgame detection and classification from chess game PGNs."""

import logging
from dataclasses import dataclass
from typing import Optional

import chess

from game_utils import game_result, COLOR_MAP
from pgn_parser import PGNParser

logger = logging.getLogger(__name__)


# Standard piece values (pawns)
_PIECE_VALUES = {
    chess.QUEEN: 9,
    chess.ROOK: 5,
    chess.BISHOP: 3,
    chess.KNIGHT: 3,
    chess.PAWN: 1,
}

# Piece values excluding pawns (for material threshold definition)
_PIECE_VALUES_NO_PAWNS = {
    chess.QUEEN: 9,
    chess.ROOK: 5,
    chess.BISHOP: 3,
    chess.KNIGHT: 3,
}

# All supported endgame definitions
ENDGAME_DEFINITIONS = ("queens-off", "minor-or-queen", "material")

# Default material threshold for the "material" definition
DEFAULT_MATERIAL_THRESHOLD = 9


@dataclass
class EndgameInfo:
    """Per-game endgame classification."""
    endgame_type: str          # "R vs R", "Pawn", "Q vs RR", etc.
    endgame_ply: int           # ply at which endgame was first detected
    material_balance: str      # "equal", "up", "down"
    my_result: str             # "win", "loss", "draw"
    fen_at_endgame: str = ""   # FEN when endgame was first detected
    game_url: str = ""         # link to the game
    material_diff: int = 0     # my_material - opponent_material (in pawns)
    my_clock: Optional[float] = None    # seconds left on my clock at endgame
    opp_clock: Optional[float] = None   # seconds left on opponent's clock


class EndgameClassifier:
    """Detects and classifies endgames from chess games."""

    @staticmethod
    def is_endgame(board, definition="minor-or-queen", material_threshold=DEFAULT_MATERIAL_THRESHOLD):
        """Check if a position is an endgame using the given definition.

        Definitions:
        - "queens-off": no queens remain on the board
        - "minor-or-queen": no queens, or each side with a queen has
          at most 1 minor piece and no rooks (default)
        - "material": each side has <= material_threshold points of
          non-pawn, non-king material (Q=9, R=5, B=3, N=3)
        """
        if definition == "queens-off":
            return (len(board.pieces(chess.QUEEN, chess.WHITE)) == 0
                    and len(board.pieces(chess.QUEEN, chess.BLACK)) == 0)

        if definition == "material":
            for color in (chess.WHITE, chess.BLACK):
                piece_material = sum(
                    len(board.pieces(pt, color)) * val
                    for pt, val in _PIECE_VALUES_NO_PAWNS.items()
                )
                if piece_material > material_threshold:
                    return False
            return True

        # Default: "minor-or-queen"
        w_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
        b_queens = len(board.pieces(chess.QUEEN, chess.BLACK))

        if w_queens == 0 and b_queens == 0:
            return True

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

        Returns (endgame_type, material_balance, material_diff).
        """
        my_c = COLOR_MAP[my_color]
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

        material_diff = my_mat - opp_mat

        if material_diff > 0:
            material_balance = "up"
        elif material_diff < 0:
            material_balance = "down"
        else:
            material_balance = "equal"

        return endgame_type, material_balance, material_diff

    @staticmethod
    def _replay_moves(game):
        """Parse PGN and replay moves, yielding state after each push.

        Yields (ply, board, last_clock) tuples. The board is mutated in
        place — callers must not store references across iterations.

        Returns None (via StopIteration) if the PGN is missing, empty,
        or contains an illegal move.
        """
        if not game.pgn:
            return

        try:
            moves_with_clocks = PGNParser.parse_moves_with_clocks(game.pgn)
        except Exception:
            logger.warning("Failed to parse PGN for endgame analysis: %s",
                           getattr(game, 'game_url', 'unknown'))
            return
        if not moves_with_clocks:
            return

        board = chess.Board()
        last_clock = {chess.WHITE: None, chess.BLACK: None}

        for ply, (move, clock) in enumerate(moves_with_clocks):
            if move not in board.legal_moves:
                logger.warning("Skipping game with illegal move %s at ply %d: %s",
                               move.uci(), ply, game.game_url or 'no URL')
                return

            side_that_moved = chess.WHITE if ply % 2 == 0 else chess.BLACK
            if clock is not None:
                last_clock[side_that_moved] = clock

            board.push(move)
            yield ply, board, last_clock

    @classmethod
    def _build_endgame_info(cls, game, board, ply, last_clock, my_c):
        """Create an EndgameInfo from the current board state."""
        endgame_type, material_balance, material_diff = (
            cls.classify_position(board, game.my_color))
        return EndgameInfo(
            endgame_type=endgame_type,
            endgame_ply=ply,
            material_balance=material_balance,
            my_result=game_result(game),
            fen_at_endgame=board.fen(),
            game_url=game.game_url or "",
            material_diff=material_diff,
            my_clock=last_clock[my_c],
            opp_clock=last_clock[not my_c],
        )

    @classmethod
    def analyze_game(cls, game, definition="minor-or-queen",
                     material_threshold=DEFAULT_MATERIAL_THRESHOLD):
        """Analyze a single game for endgame classification.

        Returns EndgameInfo if the game reached an endgame, None otherwise.
        """
        my_c = COLOR_MAP.get(game.my_color, chess.WHITE)

        for ply, board, last_clock in cls._replay_moves(game):
            if cls.is_endgame(board, definition, material_threshold):
                return cls._build_endgame_info(game, board, ply, last_clock, my_c)

        return None

    @classmethod
    def analyze_game_all(cls, game,
                         material_threshold=DEFAULT_MATERIAL_THRESHOLD):
        """Analyze a single game with all endgame definitions.

        Returns dict mapping definition name -> EndgameInfo (or None).
        Replays the PGN once; checks all definitions at each ply.
        Also captures clock times at the moment each endgame is detected.
        """
        my_c = COLOR_MAP.get(game.my_color, chess.WHITE)
        results = {}
        remaining = set(ENDGAME_DEFINITIONS)

        for ply, board, last_clock in cls._replay_moves(game):
            for defn in list(remaining):
                if cls.is_endgame(board, defn, material_threshold):
                    results[defn] = cls._build_endgame_info(
                        game, board, ply, last_clock, my_c)
                    remaining.discard(defn)

            if not remaining:
                break

        for defn in remaining:
            results[defn] = None

        return results

    @classmethod
    def _aggregate_infos(cls, infos_with_games):
        """Aggregate a list of (EndgameInfo, game) pairs into grouped stats.

        Returns a list of dicts sorted by game count descending.
        Each entry also includes an ``all_games`` list with per-game data
        (sorted most-recent first) for the "show all games" detail page.
        """
        counts = {}
        representatives = {}
        clock_data = {}  # key -> list of (my_clock, opp_clock) pairs
        all_games = {}   # key -> list of per-game dicts

        for info, game in infos_with_games:
            key = (info.endgame_type, info.material_balance)
            if key not in counts:
                counts[key] = {"wins": 0, "losses": 0, "draws": 0}
                clock_data[key] = []
                all_games[key] = []

            if info.my_result == "win":
                counts[key]["wins"] += 1
            elif info.my_result == "loss":
                counts[key]["losses"] += 1
            else:
                counts[key]["draws"] += 1

            if info.my_clock is not None or info.opp_clock is not None:
                clock_data[key].append((info.my_clock, info.opp_clock))

            end_time = getattr(game, "end_time", None)

            # Collect per-game data for the detail page
            all_games[key].append({
                "fen": info.fen_at_endgame,
                "game_url": info.game_url,
                "endgame_ply": info.endgame_ply,
                "my_result": info.my_result,
                "material_diff": info.material_diff,
                "my_clock": info.my_clock,
                "opp_clock": info.opp_clock,
                "end_time": end_time,
                "my_color": game.my_color,
                "time_class": getattr(game, "time_class", "") or "",
            })

            prev = representatives.get(key)
            if prev is None or (end_time and end_time > prev["end_time"]):
                representatives[key] = {
                    "fen": info.fen_at_endgame,
                    "game_url": info.game_url,
                    "color": game.my_color,
                    "end_time": end_time,
                    "material_diff": info.material_diff,
                    "endgame_ply": info.endgame_ply,
                    "opponent_name": game.black if game.my_color == "white" else game.white,
                    "time_class": getattr(game, "time_class", "") or "",
                }

        results = []
        for (eg_type, balance), c in counts.items():
            total = c["wins"] + c["losses"] + c["draws"]
            rep = representatives.get((eg_type, balance), {})

            # Average clock times (only from games that have clock data)
            clocks = clock_data.get((eg_type, balance), [])
            my_clocks = [mc for mc, _ in clocks if mc is not None]
            opp_clocks = [oc for _, oc in clocks if oc is not None]
            avg_my_clock = round(sum(my_clocks) / len(my_clocks)) if my_clocks else None
            avg_opp_clock = round(sum(opp_clocks) / len(opp_clocks)) if opp_clocks else None

            # Sort all_games by end_time descending (most recent first)
            games_list = all_games.get((eg_type, balance), [])
            games_list.sort(
                key=lambda g: g["end_time"] or 0, reverse=True)

            # Per-time-class breakdown for UI filtering
            tc_breakdown = {}
            platform_breakdown = {}
            color_breakdown = {}
            game_dates = []
            for g in games_list:
                r = g.get("my_result", "draw")
                # Time class breakdown
                tc = g.get("time_class", "")
                if tc not in tc_breakdown:
                    tc_breakdown[tc] = {"wins": 0, "losses": 0, "draws": 0}
                if r == "win":
                    tc_breakdown[tc]["wins"] += 1
                elif r == "loss":
                    tc_breakdown[tc]["losses"] += 1
                else:
                    tc_breakdown[tc]["draws"] += 1
                # Platform breakdown
                url = g.get("game_url", "")
                plat = ("chesscom" if "chess.com" in url
                        else "lichess" if "lichess.org" in url
                        else "unknown")
                if plat not in platform_breakdown:
                    platform_breakdown[plat] = {"wins": 0, "losses": 0, "draws": 0}
                platform_breakdown[plat][
                    "wins" if r == "win" else "losses" if r == "loss" else "draws"
                ] += 1
                # Color breakdown
                col = g.get("my_color", "white")
                if col not in color_breakdown:
                    color_breakdown[col] = {"wins": 0, "losses": 0, "draws": 0}
                color_breakdown[col][
                    "wins" if r == "win" else "losses" if r == "loss" else "draws"
                ] += 1
                # Game dates
                et = g.get("end_time")
                if et and hasattr(et, "strftime"):
                    game_dates.append(et.strftime("%Y-%m-%d"))

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
                "example_fen": rep.get("fen", ""),
                "example_game_url": rep.get("game_url", ""),
                "example_color": rep.get("color", "white"),
                "example_material_diff": rep.get("material_diff", 0),
                "example_endgame_ply": rep.get("endgame_ply", 0),
                "example_opponent_name": rep.get("opponent_name", ""),
                "example_time_class": rep.get("time_class", ""),
                "example_end_time": rep.get("end_time"),
                "avg_my_clock": avg_my_clock,
                "avg_opp_clock": avg_opp_clock,
                "all_games": games_list,
                "tc_breakdown": tc_breakdown,
                "platform_breakdown": platform_breakdown,
                "color_breakdown": color_breakdown,
                "game_dates": game_dates,
            })

        results.sort(key=lambda x: x["total"], reverse=True)
        return results

    @classmethod
    def aggregate(cls, games, definition="minor-or-queen",
                  material_threshold=DEFAULT_MATERIAL_THRESHOLD):
        """Analyze all games and return grouped endgame statistics.

        Returns a list of dicts sorted by game count descending.
        Each dict includes an example game (most recent) with FEN and URL.
        """
        pairs = []
        for game in games:
            info = cls.analyze_game(game, definition, material_threshold)
            if info is not None:
                pairs.append((info, game))
        return cls._aggregate_infos(pairs)

    @classmethod
    def aggregate_all(cls, games,
                      material_threshold=DEFAULT_MATERIAL_THRESHOLD):
        """Analyze all games with every definition and return grouped stats.

        Returns dict mapping definition name -> list of aggregate stat dicts.
        Replays each game only once.
        """
        per_def = {d: [] for d in ENDGAME_DEFINITIONS}

        for game in games:
            all_results = cls.analyze_game_all(game, material_threshold)
            for defn, info in all_results.items():
                if info is not None:
                    per_def[defn].append((info, game))

        return {defn: cls._aggregate_infos(pairs)
                for defn, pairs in per_def.items()}
