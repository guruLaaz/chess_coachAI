import chess
import pytest
from unittest.mock import patch

from pgn_parser import PGNParser


SAMPLE_PGN = """[Event "Live Chess"]
[Site "Chess.com"]
[White "PlayerA"]
[Black "PlayerB"]
[Result "1-0"]
[ECO "B90"]

1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 1-0"""

SHORT_PGN = """[Event "Live Chess"]
[Result "1-0"]

1. e4 e5 1-0"""

HEADER_ONLY_PGN = """[Event "Live Chess"]
[Result "*"]

*"""


class TestParseMoves:
    def test_valid_pgn_returns_moves(self):
        moves = PGNParser.parse_moves(SAMPLE_PGN)
        assert moves is not None
        assert len(moves) == 10  # 5 full moves = 10 half-moves
        assert all(isinstance(m, chess.Move) for m in moves)

    def test_first_move_is_e4(self):
        moves = PGNParser.parse_moves(SAMPLE_PGN)
        assert moves[0] == chess.Move.from_uci("e2e4")

    def test_short_pgn(self):
        moves = PGNParser.parse_moves(SHORT_PGN)
        assert moves is not None
        assert len(moves) == 2

    def test_none_input_returns_none(self):
        assert PGNParser.parse_moves(None) is None

    def test_empty_string_returns_none(self):
        assert PGNParser.parse_moves("") is None

    def test_whitespace_only_returns_none(self):
        assert PGNParser.parse_moves("   \n  ") is None

    def test_header_only_pgn_returns_none(self):
        """PGN with headers but no actual moves returns None."""
        result = PGNParser.parse_moves(HEADER_ONLY_PGN)
        assert result is None

    def test_garbage_input_returns_none(self):
        result = PGNParser.parse_moves("this is not a pgn at all")
        assert result is None

    def test_read_game_returns_none(self):
        """When chess.pgn.read_game returns None, parse_moves returns None."""
        with patch("pgn_parser.chess.pgn.read_game", return_value=None):
            assert PGNParser.parse_moves("some pgn text") is None


CLOCKS_PGN = """[Event "Live Chess"]
[Result "1-0"]

1. e4 {[%clk 0:09:58]} e5 {[%clk 0:09:55]} 2. Nf3 {[%clk 0:09:50]} Nc6 {[%clk 0:09:45]} 1-0"""


class TestParseMovesWithClocks:
    def test_returns_moves_and_clocks(self):
        result = PGNParser.parse_moves_with_clocks(CLOCKS_PGN)
        assert result is not None
        assert len(result) == 4
        for move, clock in result:
            assert isinstance(move, chess.Move)
            assert isinstance(clock, float)

    def test_first_clock_value(self):
        result = PGNParser.parse_moves_with_clocks(CLOCKS_PGN)
        _, clock = result[0]
        assert clock == 598.0  # 9:58 = 598 seconds

    def test_no_clock_annotations_returns_none_clocks(self):
        result = PGNParser.parse_moves_with_clocks(SHORT_PGN)
        assert result is not None
        for move, clock in result:
            assert isinstance(move, chess.Move)
            assert clock is None

    def test_none_input_returns_none(self):
        assert PGNParser.parse_moves_with_clocks(None) is None

    def test_empty_string_returns_none(self):
        assert PGNParser.parse_moves_with_clocks("") is None

    def test_header_only_returns_none(self):
        assert PGNParser.parse_moves_with_clocks(HEADER_ONLY_PGN) is None

    def test_read_game_returns_none(self):
        """When chess.pgn.read_game returns None, parse_moves_with_clocks returns None."""
        with patch("pgn_parser.chess.pgn.read_game", return_value=None):
            assert PGNParser.parse_moves_with_clocks("some pgn text") is None


class TestReplayToPosition:
    def test_replay_to_first_move(self):
        board = PGNParser.replay_to_position(SAMPLE_PGN, 0)
        assert board is not None
        # After 1. e4, it's black's turn
        assert board.turn == chess.BLACK
        # e4 pawn should be on e4
        assert board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)

    def test_replay_to_second_move(self):
        board = PGNParser.replay_to_position(SAMPLE_PGN, 1)
        assert board is not None
        # After 1. e4 c5, it's white's turn
        assert board.turn == chess.WHITE
        assert board.piece_at(chess.C5) == chess.Piece(chess.PAWN, chess.BLACK)

    def test_replay_to_last_move(self):
        board = PGNParser.replay_to_position(SAMPLE_PGN, 9)
        assert board is not None

    def test_negative_index_returns_none(self):
        assert PGNParser.replay_to_position(SAMPLE_PGN, -1) is None

    def test_index_out_of_range_returns_none(self):
        assert PGNParser.replay_to_position(SAMPLE_PGN, 999) is None

    def test_none_pgn_returns_none(self):
        assert PGNParser.replay_to_position(None, 0) is None

    def test_empty_pgn_returns_none(self):
        assert PGNParser.replay_to_position("", 0) is None

    def test_read_game_returns_none(self):
        """When chess.pgn.read_game returns None, replay_to_position returns None."""
        with patch("pgn_parser.chess.pgn.read_game", return_value=None):
            assert PGNParser.replay_to_position("some pgn text", 0) is None
