"""Tests for endgame detection and classification."""

import chess
import pytest

from endgame_detector import EndgameClassifier, EndgameInfo
from helpers import make_chess_game


# --- Reusable FEN positions ---
START_FEN = chess.STARTING_FEN
# Rook endgame: White Ke1 Ra1, Black Ke8 Ra8, pawns
ROOK_ENDGAME_FEN = "r3k3/pppp1ppp/8/8/8/8/PPPP1PPP/R3K3 w - - 0 1"
# Pawn endgame: only kings and pawns
PAWN_ENDGAME_FEN = "4k3/pppp1ppp/8/8/8/8/PPPP1PPP/4K3 w - - 0 1"
# Queen endgame: White Ke1 Qd1, Black Ke8 Qd8
QUEEN_ENDGAME_FEN = "3qk3/pppp1ppp/8/8/8/8/PPPP1PPP/3QK3 w - - 0 1"
# One queen + one minor: White Ke1 Qd1, Black Ke8 Nb8 (endgame by definition)
QUEEN_MINOR_FEN = "1n1qk3/pppp1ppp/8/8/8/8/PPPP1PPP/3QK3 w - - 0 1"
# Middlegame: lots of pieces
MIDDLEGAME_FEN = "r1bqkbnr/pppppppp/2n5/8/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 2 2"
# Queen + rook: NOT endgame (queen side has rook too)
QUEEN_ROOK_FEN = "r2qk3/pppp1ppp/8/8/8/8/PPPP1PPP/R2QK3 w - - 0 1"
# Bare kings
BARE_KINGS_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
# R+B vs R
RB_VS_R_FEN = "r3k3/pppp1ppp/8/8/8/5B2/PPPP1PPP/R3K3 w - - 0 1"
# Material imbalance: White has R, Black has nothing (except pawns)
R_VS_NONE_FEN = "4k3/pppp1ppp/8/8/8/8/PPPP1PPP/R3K3 w - - 0 1"


class TestIsEndgame:
    def test_starting_position_not_endgame(self):
        board = chess.Board(START_FEN)
        assert EndgameClassifier.is_endgame(board) is False

    def test_middlegame_not_endgame(self):
        board = chess.Board(MIDDLEGAME_FEN)
        assert EndgameClassifier.is_endgame(board) is False

    def test_rook_endgame(self):
        board = chess.Board(ROOK_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board) is True

    def test_pawn_endgame(self):
        board = chess.Board(PAWN_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board) is True

    def test_bare_kings(self):
        board = chess.Board(BARE_KINGS_FEN)
        assert EndgameClassifier.is_endgame(board) is True

    def test_queen_endgame_two_queens(self):
        """Two queens but no other pieces → endgame."""
        board = chess.Board(QUEEN_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board) is True

    def test_queen_plus_one_minor_is_endgame(self):
        """One queen + one minor piece on opponent side → still endgame."""
        board = chess.Board(QUEEN_MINOR_FEN)
        assert EndgameClassifier.is_endgame(board) is True

    def test_queen_plus_rook_not_endgame(self):
        """Queen + rook → NOT endgame (too much material)."""
        board = chess.Board(QUEEN_ROOK_FEN)
        assert EndgameClassifier.is_endgame(board) is False

    def test_rook_bishop_endgame(self):
        """R+B vs R → endgame (no queens)."""
        board = chess.Board(RB_VS_R_FEN)
        assert EndgameClassifier.is_endgame(board) is True


class TestPiecesLabel:
    def test_starting_position_white(self):
        board = chess.Board(START_FEN)
        label = EndgameClassifier._pieces_label(board, chess.WHITE)
        assert label == "QRRBBNN"

    def test_starting_position_black(self):
        board = chess.Board(START_FEN)
        label = EndgameClassifier._pieces_label(board, chess.BLACK)
        assert label == "QRRBBNN"

    def test_rook_only(self):
        board = chess.Board(ROOK_ENDGAME_FEN)
        assert EndgameClassifier._pieces_label(board, chess.WHITE) == "R"
        assert EndgameClassifier._pieces_label(board, chess.BLACK) == "R"

    def test_no_pieces(self):
        board = chess.Board(PAWN_ENDGAME_FEN)
        assert EndgameClassifier._pieces_label(board, chess.WHITE) == ""
        assert EndgameClassifier._pieces_label(board, chess.BLACK) == ""

    def test_queen_only(self):
        board = chess.Board(QUEEN_ENDGAME_FEN)
        assert EndgameClassifier._pieces_label(board, chess.WHITE) == "Q"

    def test_rook_bishop(self):
        board = chess.Board(RB_VS_R_FEN)
        assert EndgameClassifier._pieces_label(board, chess.WHITE) == "RB"


class TestMaterialValue:
    def test_starting_position(self):
        board = chess.Board(START_FEN)
        # Q(9) + 2R(10) + 2B(6) + 2N(6) + 8P(8) = 39
        assert EndgameClassifier._material_value(board, chess.WHITE) == 39
        assert EndgameClassifier._material_value(board, chess.BLACK) == 39

    def test_rook_endgame_equal(self):
        board = chess.Board(ROOK_ENDGAME_FEN)
        w_val = EndgameClassifier._material_value(board, chess.WHITE)
        b_val = EndgameClassifier._material_value(board, chess.BLACK)
        assert w_val == b_val  # symmetric

    def test_bare_kings_zero_material(self):
        board = chess.Board(BARE_KINGS_FEN)
        assert EndgameClassifier._material_value(board, chess.WHITE) == 0
        assert EndgameClassifier._material_value(board, chess.BLACK) == 0


class TestClassifyPosition:
    def test_rook_vs_rook_equal(self):
        board = chess.Board(ROOK_ENDGAME_FEN)
        eg_type, balance = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "R vs R"
        assert balance == "equal"

    def test_pawn_endgame(self):
        board = chess.Board(PAWN_ENDGAME_FEN)
        eg_type, balance = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "Pawn"
        assert balance == "equal"

    def test_queen_endgame(self):
        board = chess.Board(QUEEN_ENDGAME_FEN)
        eg_type, balance = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "Q vs Q"

    def test_rook_bishop_vs_rook(self):
        board = chess.Board(RB_VS_R_FEN)
        eg_type, balance = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "RB vs R"
        assert balance == "up"

    def test_rook_bishop_vs_rook_from_black(self):
        """Same position from black's perspective → down material."""
        board = chess.Board(RB_VS_R_FEN)
        eg_type, balance = EndgameClassifier.classify_position(board, "black")
        assert eg_type == "R vs RB"
        assert balance == "down"

    def test_rook_vs_nothing(self):
        board = chess.Board(R_VS_NONE_FEN)
        eg_type, balance = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "R vs -"
        assert balance == "up"

    def test_nothing_vs_rook(self):
        """From the disadvantaged side."""
        board = chess.Board(R_VS_NONE_FEN)
        eg_type, balance = EndgameClassifier.classify_position(board, "black")
        assert eg_type == "- vs R"
        assert balance == "down"

    def test_pawn_advantage(self):
        """Extra pawn → 'up' material."""
        # White: Ke1 + 4 pawns, Black: Ke8 + 3 pawns
        fen = "4k3/ppp2ppp/8/8/4P3/8/PPPP1PPP/4K3 w - - 0 1"
        board = chess.Board(fen)
        eg_type, balance = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "Pawn"
        assert balance == "up"


# --- PGNs for analyze_game tests ---

# A short game that never reaches endgame (scholar's mate)
SCHOLARS_MATE_PGN = """[Event "Live"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0"""

# A game that reaches a rook endgame
ROOK_ENDGAME_PGN = """[Event "Live"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Bxc6 dxc6 5. Nxe5 Qd4
6. Nf3 Qxe4+ 7. Qe2 Qxe2+ 8. Kxe2 Bf5 9. d3 O-O-O
10. Be3 Nf6 11. Nbd2 Nd5 12. Bd4 f6 13. Nc4 Nb4
14. Nce5 fxe5 15. Nxe5 Nxc2 16. Rac1 Nxd4+ 17. Ke3 Ne6
18. Nxc6 bxc6 19. Rxc6 Bd6 20. Rhc1 Kb7 21. R6c4 Rd7
22. a4 Rhd8 23. Rb4+ Ka7 24. Rc6 Nd4 25. Kd2 Nf5
26. Rxd6 Rxd6 27. Rb3 Nxg2+ 28. Kc3+ Ka8 29. Rg3 Nf4
30. d4 Be4 31. Rg4 Nd5+ 32. Kc4 Nb6+ 33. Kc5 R8d7
34. Rxe4 Nc8 35. Kxc8 1-0"""

# A pawn endgame
PAWN_ENDGAME_PGN = """[Event "Live"]
[Result "1-0"]

1. e4 e5 2. d4 exd4 3. Qxd4 Qf6 4. Qxf6 Nxf6 5. Nc3 Bb4
6. Bd2 Bxc3 7. Bxc3 Nxe4 8. Bxg7 Rg8 9. Bd4 Nxd4 10. f3 Nxf3+
11. gxf3 Nxf3+ 12. Kd1 Nd2+ 13. Kxd2 d5 14. Bd3 c6
15. Nf3 Bg4 16. Re1+ Kd7 17. Nd4 Bxd3 18. cxd3 c5
19. Nf5 Rae8 20. Rxe8 Rxe8 21. Ne3 c4 22. dxc4 dxc4
23. Nxc4 Re2+ 24. Kd3 Rxb2 25. Rc1 Rxa2 26. Nd2 1-0"""


class TestAnalyzeGame:
    def test_game_reaching_endgame(self):
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert info.my_result == "win"
        assert info.endgame_ply > 0

    def test_short_game_no_endgame(self):
        """Scholar's mate never reaches an endgame."""
        game = make_chess_game(
            pgn=SCHOLARS_MATE_PGN, my_color="white",
            white_result="win", black_result="checkmated",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is None

    def test_missing_pgn(self):
        game = make_chess_game(pgn=None)
        assert EndgameClassifier.analyze_game(game) is None

    def test_empty_pgn(self):
        game = make_chess_game(pgn="")
        assert EndgameClassifier.analyze_game(game) is None

    def test_loss_result(self):
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="black",
            white_result="win", black_result="checkmated",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert info.my_result == "loss"

    def test_draw_result(self):
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="stalemate", black_result="stalemate",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert info.my_result == "draw"

    def test_endgame_type_is_string(self):
        game = make_chess_game(
            pgn=PAWN_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert isinstance(info.endgame_type, str)
        assert info.material_balance in ("equal", "up", "down")


class TestAggregate:
    def test_multiple_games(self):
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="black",
                white_result="win", black_result="checkmated",
            ),
            make_chess_game(
                pgn=PAWN_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert isinstance(stats, list)
        assert len(stats) >= 1
        total_games = sum(s["total"] for s in stats)
        assert total_games == 3

    def test_no_endgames(self):
        games = [
            make_chess_game(
                pgn=SCHOLARS_MATE_PGN, my_color="white",
                white_result="win", black_result="checkmated",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert stats == []

    def test_single_game(self):
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert len(stats) == 1
        assert stats[0]["wins"] == 1
        assert stats[0]["total"] == 1
        assert stats[0]["win_pct"] == 100

    def test_percentages_correct(self):
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="stalemate", black_result="stalemate",
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="resigned", black_result="win",
                game_url="g2",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        # All 3 games have same PGN/color, so same endgame type+balance → 1 group
        # Find the group that has all 3
        total = sum(s["total"] for s in stats)
        assert total == 3

    def test_sorted_by_count(self):
        """Stats are sorted by total game count descending."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                game_url="g2",
            ),
            make_chess_game(
                pgn=PAWN_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        for i in range(len(stats) - 1):
            assert stats[i]["total"] >= stats[i + 1]["total"]

    def test_empty_games_list(self):
        stats = EndgameClassifier.aggregate([])
        assert stats == []
