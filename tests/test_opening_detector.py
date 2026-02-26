import chess
import chess.polyglot
from unittest.mock import patch, MagicMock

from opening_detector import OpeningDetector, DeviationResult


def _make_entry(move):
    """Create a mock polyglot entry with the given move."""
    entry = MagicMock()
    entry.move = move
    return entry


class FakeReader:
    """A fake polyglot reader that returns pre-configured book moves."""

    def __init__(self, book_moves_by_fen=None):
        """
        book_moves_by_fen: dict mapping FEN (board only) → list of chess.Move
        If None, defaults to empty (no book moves).
        """
        self.book_moves_by_fen = book_moves_by_fen or {}

    def find_all(self, board):
        fen = board.fen()
        moves = self.book_moves_by_fen.get(fen, [])
        return [_make_entry(m) for m in moves]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _starting_fen():
    return chess.Board().fen()


def _fen_after_moves(*uci_moves):
    board = chess.Board()
    for m in uci_moves:
        board.push(chess.Move.from_uci(m))
    return board.fen()


class TestFindDeviation:
    def test_empty_moves_returns_none(self):
        detector = OpeningDetector("dummy_path")
        with patch("opening_detector.chess.polyglot.open_reader"):
            assert detector.find_deviation([]) is None

    def test_first_move_not_in_book(self):
        """White plays a move not in the book on ply 0."""
        fake = FakeReader(book_moves_by_fen={})  # empty book

        detector = OpeningDetector("dummy_path")
        moves = [chess.Move.from_uci("e2e4")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result is not None
        assert result.deviation_ply == 0
        assert result.deviating_side == "white"
        assert result.is_fully_booked is False

    def test_deviation_on_blacks_move(self):
        """Book has 1.e4 but black plays something not in the book."""
        book = {
            _starting_fen(): [chess.Move.from_uci("e2e4")],
            # No book entry for the position after 1.e4
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        moves = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("c7c5")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result.deviation_ply == 1
        assert result.deviating_side == "black"
        assert result.is_fully_booked is False

    def test_all_moves_in_book(self):
        """Every move is in the book → is_fully_booked = True."""
        book = {
            _starting_fen(): [chess.Move.from_uci("e2e4")],
            _fen_after_moves("e2e4"): [chess.Move.from_uci("e7e5")],
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        moves = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result.is_fully_booked is True
        assert result.deviation_ply == 2
        assert result.deviating_side == "none"

    def test_deviation_on_third_ply(self):
        """Book covers first 2 plies, deviation happens on ply 2 (white's 2nd move)."""
        book = {
            _starting_fen(): [chess.Move.from_uci("e2e4")],
            _fen_after_moves("e2e4"): [chess.Move.from_uci("e7e5")],
            # No entry for position after 1.e4 e5
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        moves = [
            chess.Move.from_uci("e2e4"),
            chess.Move.from_uci("e7e5"),
            chess.Move.from_uci("g1f3"),
        ]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result.deviation_ply == 2
        assert result.deviating_side == "white"
        assert result.is_fully_booked is False

    def test_board_at_deviation_is_correct(self):
        """The board_at_deviation should be the position BEFORE the deviating move."""
        book = {
            _starting_fen(): [chess.Move.from_uci("e2e4")],
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        moves = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("c7c5")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        # Board should be the position after 1.e4 (before black's deviation)
        expected = chess.Board()
        expected.push(chess.Move.from_uci("e2e4"))
        assert result.board_at_deviation.fen() == expected.fen()

    def test_played_move_captured_on_deviation(self):
        """played_move should be the move that deviated from the book."""
        book = {
            _starting_fen(): [chess.Move.from_uci("e2e4")],
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        moves = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("c7c5")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result.played_move == chess.Move.from_uci("c7c5")

    def test_book_moves_captured_on_deviation(self):
        """book_moves should list what the book offered at the deviation point."""
        book = {
            _starting_fen(): [chess.Move.from_uci("e2e4")],
            _fen_after_moves("e2e4"): [
                chess.Move.from_uci("e7e5"),
                chess.Move.from_uci("c7c5"),
            ],
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        # Black plays d7d5 (not in book)
        moves = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("d7d5")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result.played_move == chess.Move.from_uci("d7d5")
        assert set(result.book_moves) == {
            chess.Move.from_uci("e7e5"),
            chess.Move.from_uci("c7c5"),
        }

    def test_fully_booked_has_no_played_move(self):
        """When all moves are in book, played_move should be None."""
        book = {
            _starting_fen(): [chess.Move.from_uci("e2e4")],
            _fen_after_moves("e2e4"): [chess.Move.from_uci("e7e5")],
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        moves = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result.is_fully_booked is True
        assert result.played_move is None
        assert result.book_moves == []

    def test_first_move_deviation_captures_empty_book(self):
        """When book is empty, deviation at ply 0 should capture empty book_moves."""
        fake = FakeReader(book_moves_by_fen={})

        detector = OpeningDetector("dummy_path")
        moves = [chess.Move.from_uci("e2e4")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        assert result.played_move == chess.Move.from_uci("e2e4")
        assert result.book_moves == []

    def test_multiple_book_moves_available(self):
        """Book has multiple candidate moves; game plays one of them → no deviation."""
        book = {
            _starting_fen(): [
                chess.Move.from_uci("e2e4"),
                chess.Move.from_uci("d2d4"),
                chess.Move.from_uci("c2c4"),
            ],
        }
        fake = FakeReader(book_moves_by_fen=book)

        detector = OpeningDetector("dummy_path")
        # Player plays d4, which is in the book
        moves = [chess.Move.from_uci("d2d4")]

        with patch("opening_detector.chess.polyglot.open_reader", return_value=fake):
            result = detector.find_deviation(moves)

        # d4 is in book, so all moves are booked
        assert result.is_fully_booked is True
