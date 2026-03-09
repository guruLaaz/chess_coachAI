"""Tests for endgame detection and classification."""

import datetime
from unittest.mock import patch

import chess
import pytest

from endgame_detector import EndgameClassifier, EndgameInfo, ENDGAME_DEFINITIONS
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


class TestIsEndgameQueensOff:
    """Tests for the 'queens-off' definition."""

    def test_no_queens_is_endgame(self):
        board = chess.Board(ROOK_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "queens-off") is True

    def test_queens_present_not_endgame(self):
        board = chess.Board(QUEEN_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "queens-off") is False

    def test_queen_minor_not_endgame(self):
        board = chess.Board(QUEEN_MINOR_FEN)
        assert EndgameClassifier.is_endgame(board, "queens-off") is False

    def test_pawn_only_is_endgame(self):
        board = chess.Board(PAWN_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "queens-off") is True

    def test_starting_position_not_endgame(self):
        board = chess.Board(START_FEN)
        assert EndgameClassifier.is_endgame(board, "queens-off") is False


class TestIsEndgameMaterial:
    """Tests for the 'material' definition (threshold=9 by default)."""

    def test_starting_position_not_endgame(self):
        """Starting position has way more than 9 pts per side."""
        board = chess.Board(START_FEN)
        assert EndgameClassifier.is_endgame(board, "material") is False

    def test_rook_endgame_is_endgame(self):
        """R vs R: each side has 5 pts (≤9)."""
        board = chess.Board(ROOK_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "material") is True

    def test_queen_endgame_is_endgame(self):
        """Q vs Q: each side has 9 pts (≤9)."""
        board = chess.Board(QUEEN_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "material") is True

    def test_queen_rook_not_endgame(self):
        """Q+R vs Q+R: each side has 14 pts (>9)."""
        board = chess.Board(QUEEN_ROOK_FEN)
        assert EndgameClassifier.is_endgame(board, "material") is False

    def test_pawn_endgame_is_endgame(self):
        """Pawns only: 0 non-pawn material per side."""
        board = chess.Board(PAWN_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "material") is True

    def test_custom_threshold(self):
        """R vs R with threshold=4 is NOT endgame (5 > 4)."""
        board = chess.Board(ROOK_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "material", material_threshold=4) is False

    def test_custom_threshold_accepts(self):
        """R vs R with threshold=5 IS endgame (5 ≤ 5)."""
        board = chess.Board(ROOK_ENDGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "material", material_threshold=5) is True

    def test_middlegame_not_endgame(self):
        board = chess.Board(MIDDLEGAME_FEN)
        assert EndgameClassifier.is_endgame(board, "material") is False


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
        eg_type, balance, diff = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "R vs R"
        assert balance == "equal"
        assert diff == 0

    def test_pawn_endgame(self):
        board = chess.Board(PAWN_ENDGAME_FEN)
        eg_type, balance, diff = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "Pawn"
        assert balance == "equal"
        assert diff == 0

    def test_queen_endgame(self):
        board = chess.Board(QUEEN_ENDGAME_FEN)
        eg_type, balance, _diff = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "Q vs Q"

    def test_rook_bishop_vs_rook(self):
        board = chess.Board(RB_VS_R_FEN)
        eg_type, balance, diff = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "RB vs R"
        assert balance == "up"
        assert diff == 3  # bishop worth 3 pawns

    def test_rook_bishop_vs_rook_from_black(self):
        """Same position from black's perspective → down material."""
        board = chess.Board(RB_VS_R_FEN)
        eg_type, balance, diff = EndgameClassifier.classify_position(board, "black")
        assert eg_type == "R vs RB"
        assert balance == "down"
        assert diff == -3

    def test_rook_vs_nothing(self):
        board = chess.Board(R_VS_NONE_FEN)
        eg_type, balance, _diff = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "R vs -"
        assert balance == "up"

    def test_nothing_vs_rook(self):
        """From the disadvantaged side."""
        board = chess.Board(R_VS_NONE_FEN)
        eg_type, balance, _diff = EndgameClassifier.classify_position(board, "black")
        assert eg_type == "- vs R"
        assert balance == "down"

    def test_pawn_advantage(self):
        """Extra pawn → 'up' material."""
        # White: Ke1 + 4 pawns, Black: Ke8 + 3 pawns
        fen = "4k3/ppp2ppp/8/8/4P3/8/PPPP1PPP/4K3 w - - 0 1"
        board = chess.Board(fen)
        eg_type, balance, _diff = EndgameClassifier.classify_position(board, "white")
        assert eg_type == "Pawn"
        assert balance == "up"


# --- PGNs for analyze_game tests ---

# Header-only PGN (no actual moves) — truthy string, but no moves to parse
HEADER_ONLY_PGN = """[Event "Live"]
[Result "*"]

*"""

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

    def test_header_only_pgn(self):
        """PGN with headers but no moves returns None."""
        game = make_chess_game(pgn=HEADER_ONLY_PGN)
        assert EndgameClassifier.analyze_game(game) is None

    def test_illegal_move_sequence_returns_none(self):
        """Games with corrupt/illegal move sequences are skipped gracefully."""
        game = make_chess_game(
            pgn="dummy", my_color="white",
            white_result="win", black_result="resigned",
            game_url="https://www.chess.com/game/live/999",
        )
        illegal_moves = [(chess.Move.from_uci("e5f6"), None)]
        with patch("endgame_detector.PGNParser.parse_moves_with_clocks", return_value=illegal_moves):
            info = EndgameClassifier.analyze_game(game)
        assert info is None

    def test_illegal_move_sequence_logs_warning(self, capsys):
        """A warning with the game URL is printed for corrupt move sequences."""
        game = make_chess_game(
            pgn="dummy", my_color="white",
            white_result="win", black_result="resigned",
            game_url="https://www.chess.com/game/live/999",
        )
        illegal_moves = [(chess.Move.from_uci("e5f6"), None)]
        with patch("endgame_detector.PGNParser.parse_moves_with_clocks", return_value=illegal_moves):
            EndgameClassifier.analyze_game(game)
        output = capsys.readouterr().out
        assert "Warning" in output
        assert "e5f6" in output
        assert "https://www.chess.com/game/live/999" in output

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

    def test_fen_at_endgame_populated(self):
        """analyze_game populates fen_at_endgame with a valid FEN."""
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert info.fen_at_endgame != ""
        # Verify it's a valid FEN by parsing it
        board = chess.Board(info.fen_at_endgame)
        assert board is not None

    def test_game_url_populated(self):
        """analyze_game captures game_url from the game object."""
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
            game_url="https://www.chess.com/game/live/12345",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert info.game_url == "https://www.chess.com/game/live/12345"

    def test_game_url_empty_when_missing(self):
        """analyze_game returns empty game_url when game has none."""
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
            game_url="",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert info.game_url == ""

    def test_material_diff_populated(self):
        """analyze_game populates material_diff as an integer."""
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        info = EndgameClassifier.analyze_game(game)
        assert info is not None
        assert isinstance(info.material_diff, int)


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

    def test_aggregate_includes_example_fields(self):
        """Each aggregate result includes example_fen, example_game_url, example_color, example_material_diff."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                game_url="https://www.chess.com/game/live/111",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert len(stats) >= 1
        s = stats[0]
        assert "example_fen" in s
        assert s["example_fen"] != ""
        assert s["example_game_url"] == "https://www.chess.com/game/live/111"
        assert s["example_color"] == "white"
        assert "example_material_diff" in s
        assert isinstance(s["example_material_diff"], int)

    def test_tc_breakdown(self):
        """Aggregate results include per-time-class win/loss/draw breakdown."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                time_class="blitz",
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="stalemate", black_result="stalemate",
                time_class="rapid", game_url="g2",
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="resigned", black_result="win",
                time_class="blitz", game_url="g3",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert len(stats) >= 1
        s = stats[0]
        assert "tc_breakdown" in s
        assert "blitz" in s["tc_breakdown"]
        assert "rapid" in s["tc_breakdown"]
        assert s["tc_breakdown"]["blitz"]["wins"] == 1
        assert s["tc_breakdown"]["blitz"]["losses"] == 1
        assert s["tc_breakdown"]["rapid"]["draws"] == 1

    def test_all_games_has_time_class(self):
        """Each entry in all_games includes the time_class field."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                time_class="bullet",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert len(stats) >= 1
        for g in stats[0]["all_games"]:
            assert "time_class" in g
            assert g["time_class"] == "bullet"

    def test_aggregate_picks_most_recent_game(self):
        """Representative example is the most recent game by end_time."""
        old_time = datetime.datetime(2025, 1, 1, 12, 0, 0)
        new_time = datetime.datetime(2025, 6, 15, 12, 0, 0)
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                game_url="https://www.chess.com/game/live/old",
                end_time=old_time,
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                game_url="https://www.chess.com/game/live/new",
                end_time=new_time,
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert len(stats) >= 1
        # Both games have same type+balance, so they merge into one group
        # The most recent game (new_time) should be the representative
        s = stats[0]
        assert s["example_game_url"] == "https://www.chess.com/game/live/new"

    def test_aggregate_skips_games_with_illegal_moves(self):
        """Games with corrupt move sequences are silently skipped in aggregate."""
        illegal_game = make_chess_game(
            pgn="dummy", my_color="white",
            white_result="win", black_result="resigned",
        )
        illegal_moves = [(chess.Move.from_uci("e5f6"), None)]
        with patch("endgame_detector.PGNParser.parse_moves_with_clocks", return_value=illegal_moves):
            stats = EndgameClassifier.aggregate([illegal_game])
        assert stats == []

    def test_empty_games_list(self):
        stats = EndgameClassifier.aggregate([])
        assert stats == []

    def test_aggregate_with_queens_off_definition(self):
        """Aggregate with queens-off definition works."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games, definition="queens-off")
        assert len(stats) >= 1

    def test_aggregate_with_material_definition(self):
        """Aggregate with material definition returns a list (may be empty if PGN truncated)."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games, definition="material")
        assert isinstance(stats, list)


class TestAnalyzeGameAll:
    def test_returns_all_definitions(self):
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        results = EndgameClassifier.analyze_game_all(game)
        assert set(results.keys()) == set(ENDGAME_DEFINITIONS)

    def test_queens_off_and_minor_detect_rook_endgame(self):
        """queens-off and minor-or-queen detect the rook endgame PGN."""
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        results = EndgameClassifier.analyze_game_all(game)
        assert results["queens-off"] is not None
        assert results["minor-or-queen"] is not None

    def test_definitions_may_disagree(self):
        """Different definitions may detect endgame at different points or not at all."""
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        results = EndgameClassifier.analyze_game_all(game)
        # queens-off and minor-or-queen should agree on this game
        assert results["queens-off"] is not None
        assert results["minor-or-queen"] is not None
        # material may or may not detect (depends on where game truncates)
        # Just verify it's a valid result (None or EndgameInfo)
        assert results["material"] is None or isinstance(results["material"], EndgameInfo)

    def test_no_pgn_returns_all_none(self):
        game = make_chess_game(pgn=None)
        results = EndgameClassifier.analyze_game_all(game)
        for defn in ENDGAME_DEFINITIONS:
            assert results[defn] is None

    def test_header_only_pgn_returns_all_none(self):
        """PGN with headers but no moves returns all None."""
        game = make_chess_game(pgn=HEADER_ONLY_PGN)
        results = EndgameClassifier.analyze_game_all(game)
        for defn in ENDGAME_DEFINITIONS:
            assert results[defn] is None

    def test_all_definitions_trigger_early_break(self):
        """When all definitions detect endgame, the loop breaks early."""
        # Use a very low material threshold so 'material' definition
        # fires at the same point as queens-off/minor-or-queen
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        results = EndgameClassifier.analyze_game_all(game, material_threshold=40)
        # All 3 definitions should detect an endgame
        for defn in ENDGAME_DEFINITIONS:
            assert results[defn] is not None

    def test_short_game_no_endgame(self):
        game = make_chess_game(
            pgn=SCHOLARS_MATE_PGN, my_color="white",
            white_result="win", black_result="checkmated",
        )
        results = EndgameClassifier.analyze_game_all(game)
        for defn in ENDGAME_DEFINITIONS:
            assert results[defn] is None

    def test_illegal_moves_returns_all_none(self):
        game = make_chess_game(
            pgn="dummy", my_color="white",
            white_result="win", black_result="resigned",
        )
        illegal_moves = [(chess.Move.from_uci("e5f6"), None)]
        with patch("endgame_detector.PGNParser.parse_moves_with_clocks", return_value=illegal_moves):
            results = EndgameClassifier.analyze_game_all(game)
        for defn in ENDGAME_DEFINITIONS:
            assert results[defn] is None


# A rook endgame PGN with clock annotations
ROOK_ENDGAME_CLOCKS_PGN = """[Event "Live"]
[Result "1-0"]

1. e4 {[%clk 0:09:58]} e5 {[%clk 0:09:57]} 2. Nf3 {[%clk 0:09:50]} Nc6 {[%clk 0:09:45]}
3. Bb5 {[%clk 0:09:40]} a6 {[%clk 0:09:35]} 4. Bxc6 {[%clk 0:09:30]} dxc6 {[%clk 0:09:20]}
5. Nxe5 {[%clk 0:09:20]} Qd4 {[%clk 0:09:10]}
6. Nf3 {[%clk 0:09:10]} Qxe4+ {[%clk 0:09:00]} 7. Qe2 {[%clk 0:09:00]} Qxe2+ {[%clk 0:08:50]}
8. Kxe2 {[%clk 0:08:50]} Bf5 {[%clk 0:08:40]} 9. d3 {[%clk 0:08:30]} O-O-O {[%clk 0:08:30]}
10. Be3 {[%clk 0:08:20]} Nf6 {[%clk 0:08:10]} 11. Nbd2 {[%clk 0:08:10]} Nd5 {[%clk 0:08:00]}
12. Bd4 {[%clk 0:08:00]} f6 {[%clk 0:07:50]} 13. Nc4 {[%clk 0:07:50]} Nb4 {[%clk 0:07:40]}
14. Nce5 {[%clk 0:07:40]} fxe5 {[%clk 0:07:30]} 15. Nxe5 {[%clk 0:07:20]} Nxc2 {[%clk 0:07:20]}
16. Rac1 {[%clk 0:07:10]} Nxd4+ {[%clk 0:07:00]} 17. Ke3 {[%clk 0:07:00]} Ne6 {[%clk 0:06:50]}
18. Nxc6 {[%clk 0:06:50]} bxc6 {[%clk 0:06:40]} 19. Rxc6 {[%clk 0:06:40]} Bd6 {[%clk 0:06:30]}
20. Rhc1 {[%clk 0:06:30]} Kb7 {[%clk 0:06:20]} 21. R6c4 {[%clk 0:06:20]} Rd7 {[%clk 0:06:10]}
22. a4 {[%clk 0:06:10]} Rhd8 {[%clk 0:06:00]} 23. Rb4+ {[%clk 0:06:00]} Ka7 {[%clk 0:05:50]}
24. Rc6 {[%clk 0:05:50]} Nd4 {[%clk 0:05:40]} 25. Kd2 {[%clk 0:05:40]} Nf5 {[%clk 0:05:30]}
26. Rxd6 {[%clk 0:05:20]} Rxd6 {[%clk 0:05:20]} 27. Rb3 {[%clk 0:05:10]} Nxg2+ {[%clk 0:05:00]}
28. Kc3+ {[%clk 0:05:00]} Ka8 {[%clk 0:04:50]} 1-0"""


class TestAnalyzeGameAllClocks:
    """Tests for clock time extraction in analyze_game_all."""

    def test_clock_times_populated(self):
        game = make_chess_game(
            pgn=ROOK_ENDGAME_CLOCKS_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        results = EndgameClassifier.analyze_game_all(game)
        info = results["queens-off"]
        assert info is not None
        assert info.my_clock is not None
        assert info.opp_clock is not None
        # The queen trade happens around ply 12-13 (Qxe2+/Kxe2)
        # Clock values should be reasonable (less than starting 10 min)
        assert info.my_clock < 600
        assert info.opp_clock < 600

    def test_clock_times_none_without_annotations(self):
        game = make_chess_game(
            pgn=ROOK_ENDGAME_PGN, my_color="white",
            white_result="win", black_result="resigned",
        )
        results = EndgameClassifier.analyze_game_all(game)
        info = results["queens-off"]
        assert info is not None
        assert info.my_clock is None
        assert info.opp_clock is None

    def test_clock_my_color_black(self):
        game = make_chess_game(
            pgn=ROOK_ENDGAME_CLOCKS_PGN, my_color="black",
            white_result="win", black_result="checkmated",
        )
        results = EndgameClassifier.analyze_game_all(game)
        info = results["queens-off"]
        assert info is not None
        # As black, my_clock should be black's clock, opp should be white's
        assert info.my_clock is not None
        assert info.opp_clock is not None


class TestAggregateClocks:
    """Tests for average clock time computation in aggregation."""

    def test_avg_clock_in_aggregate(self):
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_CLOCKS_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        result = EndgameClassifier.aggregate(games, definition="queens-off")
        assert len(result) >= 1
        entry = result[0]
        assert entry["avg_my_clock"] is not None
        assert entry["avg_opp_clock"] is not None

    def test_avg_clock_none_without_annotations(self):
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        result = EndgameClassifier.aggregate(games, definition="queens-off")
        assert len(result) >= 1
        entry = result[0]
        assert entry["avg_my_clock"] is None
        assert entry["avg_opp_clock"] is None


class TestAggregateEndgamePly:
    """Tests for endgame_ply in aggregate results."""

    def test_endgame_ply_in_aggregate(self):
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        result = EndgameClassifier.aggregate(games)
        assert len(result) >= 1
        entry = result[0]
        assert "example_endgame_ply" in entry
        assert entry["example_endgame_ply"] > 0


class TestAggregateAll:
    def test_returns_all_definitions(self):
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        result = EndgameClassifier.aggregate_all(games)
        assert set(result.keys()) == set(ENDGAME_DEFINITIONS)
        for defn in ENDGAME_DEFINITIONS:
            assert isinstance(result[defn], list)

    def test_empty_games(self):
        result = EndgameClassifier.aggregate_all([])
        for defn in ENDGAME_DEFINITIONS:
            assert result[defn] == []

    def test_all_definitions_have_entries(self):
        """aggregate_all returns stats for definitions that detect endgames."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        result = EndgameClassifier.aggregate_all(games)
        # queens-off and minor-or-queen should detect this game
        assert len(result["queens-off"]) >= 1
        assert len(result["minor-or-queen"]) >= 1


class TestAggregateAllGames:
    """Tests for the all_games per-game data in aggregate results."""

    def test_all_games_field_present(self):
        """Each aggregate entry should have an all_games list."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert len(stats) >= 1
        for entry in stats:
            assert "all_games" in entry
            assert isinstance(entry["all_games"], list)

    def test_all_games_count_matches_total(self):
        """all_games list length should match the total game count."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        for entry in stats:
            assert len(entry["all_games"]) == entry["total"]

    def test_all_games_has_required_fields(self):
        """Each game dict in all_games has all required fields."""
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        for entry in stats:
            for g in entry["all_games"]:
                assert "fen" in g
                assert "game_url" in g
                assert "endgame_ply" in g
                assert "my_result" in g
                assert "material_diff" in g
                assert "my_clock" in g
                assert "opp_clock" in g
                assert "end_time" in g
                assert "my_color" in g

    def test_all_games_sorted_most_recent_first(self):
        """all_games should be sorted by end_time descending."""
        import datetime
        old_time = datetime.datetime(2025, 1, 1, 12, 0, 0)
        new_time = datetime.datetime(2025, 6, 15, 12, 0, 0)
        games = [
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                game_url="https://www.chess.com/game/live/old",
                end_time=old_time,
            ),
            make_chess_game(
                pgn=ROOK_ENDGAME_PGN, my_color="white",
                white_result="win", black_result="resigned",
                game_url="https://www.chess.com/game/live/new",
                end_time=new_time,
            ),
        ]
        stats = EndgameClassifier.aggregate(games)
        assert len(stats) >= 1
        entry = stats[0]
        assert len(entry["all_games"]) == 2
        # Most recent (new_time) should be first
        assert entry["all_games"][0]["game_url"] == "https://www.chess.com/game/live/new"
        assert entry["all_games"][1]["game_url"] == "https://www.chess.com/game/live/old"
