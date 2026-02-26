import datetime
from chessgame import ChessGame
from helpers import make_game_json


class TestFromJson:
    def test_parse_as_white(self):
        data = make_game_json(white_user="Alice", black_user="Bob",
                              white_result="win", black_result="lose",
                              termination="checkmate")
        game = ChessGame.from_json(data, "Alice")

        assert game is not None
        assert game.my_color == "white"
        assert game.white == "Alice"
        assert game.black == "Bob"
        assert game.white_result == "win"
        assert game.black_result == "lose"
        assert game.termination == "checkmate"

    def test_parse_as_black(self):
        data = make_game_json(white_user="Alice", black_user="Bob",
                              white_result="lose", black_result="win",
                              termination="time")
        game = ChessGame.from_json(data, "Bob")

        assert game is not None
        assert game.my_color == "black"
        assert game.white_result == "lose"
        assert game.black_result == "win"

    def test_username_not_in_game_returns_none(self):
        data = make_game_json(white_user="Alice", black_user="Bob")
        game = ChessGame.from_json(data, "Charlie")

        assert game is None

    def test_case_insensitive_username(self):
        data = make_game_json(white_user="Alice", black_user="Bob")
        game = ChessGame.from_json(data, "aLiCe")

        assert game is not None
        assert game.my_color == "white"

    def test_end_time_parsed_from_unix(self):
        ts = int(datetime.datetime(2025, 1, 15, 10, 30, 0).timestamp())
        data = make_game_json(end_time=ts)
        game = ChessGame.from_json(data, "PlayerA")

        assert game.end_time == datetime.datetime(2025, 1, 15, 10, 30, 0)

    def test_missing_end_time_falls_back(self):
        data = make_game_json()
        data["end_time"] = None
        game = ChessGame.from_json(data, "PlayerA")

        # Should not crash; falls back to datetime.now()
        assert isinstance(game.end_time, datetime.datetime)

    def test_missing_nested_fields_no_crash(self):
        data = {"white": {}, "black": {}, "end_time": None, "termination": ""}
        game = ChessGame.from_json(data, "anyone")

        # Username doesn't match empty strings, so returns None
        assert game is None

    def test_clock_defaults_to_zero(self):
        data = make_game_json()
        game = ChessGame.from_json(data, "PlayerA")

        assert game.my_clock_left == 0
        assert game.opponent_clock_left == 0
