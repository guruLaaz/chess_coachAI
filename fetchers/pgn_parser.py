# pgn_parser.py

import io
import chess
import chess.pgn


class PGNParser:
    """Parses PGN strings into move lists and board positions."""

    @staticmethod
    def parse_moves(pgn_string):
        """Parse a PGN string and return a list of chess.Move objects.

        Returns None if the PGN is invalid or empty.
        """
        if not pgn_string or not pgn_string.strip():
            return None

        game = chess.pgn.read_game(io.StringIO(pgn_string))
        if game is None:
            return None

        moves = list(game.mainline_moves())
        return moves if moves else None

    @staticmethod
    def replay_to_position(pgn_string, move_index):
        """Replay a PGN up to move_index and return the resulting board.

        move_index is 0-based (0 = after first move, 1 = after second, etc.).
        Returns None if PGN is invalid or move_index is out of range.
        """
        if not pgn_string or not pgn_string.strip():
            return None

        game = chess.pgn.read_game(io.StringIO(pgn_string))
        if game is None:
            return None

        board = game.board()
        moves = list(game.mainline_moves())

        if move_index < 0 or move_index >= len(moves):
            return None

        for i, move in enumerate(moves):
            board.push(move)
            if i == move_index:
                break

        return board
