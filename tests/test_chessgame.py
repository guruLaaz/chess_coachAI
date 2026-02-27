import datetime
from chessgame import ChessGame
from helpers import make_game_json, make_lichess_game_json


class TestFromJson:
    def test_parse_as_white(self):
        data = make_game_json(white_user="Alice", black_user="Bob",
                              white_result="win", black_result="lose")
        game = ChessGame.from_json(data, "Alice")

        assert game is not None
        assert game.my_color == "white"
        assert game.white == "Alice"
        assert game.black == "Bob"
        assert game.white_result == "win"
        assert game.black_result == "lose"

    def test_parse_as_black(self):
        data = make_game_json(white_user="Alice", black_user="Bob",
                              white_result="lose", black_result="win")
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
        data = {"white": {}, "black": {}, "end_time": None}
        game = ChessGame.from_json(data, "anyone")

        # Username doesn't match empty strings, so returns None
        assert game is None

    def test_clock_defaults_to_zero(self):
        data = make_game_json()
        game = ChessGame.from_json(data, "PlayerA")

        assert game.my_clock_left == 0
        assert game.opponent_clock_left == 0

    def test_pgn_extracted_from_json(self):
        pgn_str = '[Event "Live"]\n\n1. e4 e5 1-0'
        data = make_game_json(pgn=pgn_str)
        game = ChessGame.from_json(data, "PlayerA")

        assert game.pgn == pgn_str

    def test_pgn_defaults_to_none(self):
        data = make_game_json()
        game = ChessGame.from_json(data, "PlayerA")

        assert game.pgn is None

    def test_eco_code_from_pgn_header(self):
        pgn_str = '[ECO "B90"]\n\n1. e4 c5 1-0'
        data = make_game_json(pgn=pgn_str)
        game = ChessGame.from_json(data, "PlayerA")

        assert game.eco_code == "B90"

    def test_eco_code_none_when_no_pgn(self):
        data = make_game_json()
        game = ChessGame.from_json(data, "PlayerA")

        assert game.eco_code is None

    def test_eco_code_none_when_no_eco_header(self):
        pgn_str = '[Event "Live"]\n\n1. e4 e5 1-0'
        data = make_game_json(pgn=pgn_str)
        game = ChessGame.from_json(data, "PlayerA")

        assert game.eco_code is None

    def test_eco_name_from_url(self):
        eco = "https://www.chess.com/openings/Sicilian-Defense-Najdorf-Variation"
        data = make_game_json(eco_url=eco)
        game = ChessGame.from_json(data, "PlayerA")

        assert game.eco_name == "Sicilian Defense Najdorf Variation"
        assert game.eco_url == eco

    def test_eco_name_empty_when_no_url(self):
        data = make_game_json()
        game = ChessGame.from_json(data, "PlayerA")

        assert game.eco_name == ""
        assert game.eco_url == ""

    def test_time_class_parsed_from_json(self):
        data = make_game_json(time_class="blitz")
        game = ChessGame.from_json(data, "PlayerA")

        assert game.time_class == "blitz"

    def test_time_class_defaults_to_none(self):
        data = make_game_json()
        game = ChessGame.from_json(data, "PlayerA")

        assert game.time_class is None

    def test_time_class_bullet(self):
        data = make_game_json(time_class="bullet")
        game = ChessGame.from_json(data, "PlayerA")
        assert game.time_class == "bullet"

    def test_time_class_rapid(self):
        data = make_game_json(time_class="rapid")
        game = ChessGame.from_json(data, "PlayerA")
        assert game.time_class == "rapid"

    def test_time_class_daily(self):
        data = make_game_json(time_class="daily")
        game = ChessGame.from_json(data, "PlayerA")
        assert game.time_class == "daily"

    def test_game_url_from_json(self):
        data = make_game_json(game_url="https://www.chess.com/game/live/123456")
        game = ChessGame.from_json(data, "PlayerA")
        assert game.game_url == "https://www.chess.com/game/live/123456"

    def test_game_url_defaults_to_empty(self):
        data = make_game_json()
        game = ChessGame.from_json(data, "PlayerA")
        assert game.game_url == ""


class TestFromLichessJson:
    def test_parse_as_white(self):
        data = make_lichess_game_json(white_user="Alice", black_user="Bob",
                                       winner="white")
        game = ChessGame.from_lichess_json(data, "Alice")
        assert game is not None
        assert game.my_color == "white"
        assert game.white_result == "win"
        assert game.black_result == "lose"

    def test_parse_as_black(self):
        data = make_lichess_game_json(white_user="Alice", black_user="Bob",
                                       winner="black")
        game = ChessGame.from_lichess_json(data, "Bob")
        assert game is not None
        assert game.my_color == "black"
        assert game.white_result == "lose"
        assert game.black_result == "win"

    def test_username_not_in_game_returns_none(self):
        data = make_lichess_game_json(white_user="Alice", black_user="Bob")
        game = ChessGame.from_lichess_json(data, "Charlie")
        assert game is None

    def test_case_insensitive_username(self):
        data = make_lichess_game_json(white_user="Alice", black_user="Bob")
        game = ChessGame.from_lichess_json(data, "aLiCe")
        assert game is not None
        assert game.my_color == "white"

    def test_draw_result(self):
        data = make_lichess_game_json(white_user="Alice", black_user="Bob",
                                       winner=None, status="stalemate")
        game = ChessGame.from_lichess_json(data, "Alice")
        assert game.white_result == "stalemate"
        assert game.black_result == "stalemate"

    def test_speed_classical_maps_to_rapid(self):
        data = make_lichess_game_json(speed="classical")
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.time_class == "rapid"

    def test_speed_correspondence_maps_to_daily(self):
        data = make_lichess_game_json(speed="correspondence")
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.time_class == "daily"

    def test_speed_blitz_unchanged(self):
        data = make_lichess_game_json(speed="blitz")
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.time_class == "blitz"

    def test_speed_ultra_bullet_maps_to_bullet(self):
        data = make_lichess_game_json(speed="ultraBullet")
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.time_class == "bullet"

    def test_game_url_format(self):
        data = make_lichess_game_json(game_id="XyZ12345")
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.game_url == "https://lichess.org/XyZ12345"

    def test_end_time_from_last_move_at(self):
        ts_ms = int(datetime.datetime(2025, 3, 10, 14, 0, 0).timestamp() * 1000)
        data = make_lichess_game_json(last_move_at=ts_ms)
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.end_time == datetime.datetime(2025, 3, 10, 14, 0, 0)

    def test_eco_code_from_opening(self):
        data = make_lichess_game_json(eco="C50", opening_name="Italian Game")
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.eco_code == "C50"
        assert game.eco_name == "Italian Game"

    def test_pgn_extracted(self):
        pgn = '[Event "Rated Blitz"]\n\n1. e4 e5 1-0'
        data = make_lichess_game_json(pgn=pgn)
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.pgn == pgn

    def test_last_move_at_absent_falls_back_to_created_at(self):
        """When lastMoveAt is missing, createdAt is used for end_time."""
        created_ms = int(datetime.datetime(2025, 5, 1, 10, 0, 0).timestamp() * 1000)
        data = make_lichess_game_json()
        del data["lastMoveAt"]
        data["createdAt"] = created_ms
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.end_time == datetime.datetime(2025, 5, 1, 10, 0, 0)

    def test_both_timestamps_absent_falls_back_to_now(self):
        """When both lastMoveAt and createdAt are absent, falls back to now()."""
        data = make_lichess_game_json()
        del data["lastMoveAt"]
        del data["createdAt"]
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert isinstance(game.end_time, datetime.datetime)

    def test_unknown_speed_passes_through(self):
        """A speed not in _LICHESS_SPEED_MAP is used as-is."""
        data = make_lichess_game_json(speed="atomic")
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.time_class == "atomic"

    def test_missing_game_id_gives_empty_url(self):
        """When 'id' is absent, game_url is empty."""
        data = make_lichess_game_json()
        del data["id"]
        game = ChessGame.from_lichess_json(data, "PlayerA")
        assert game.game_url == ""

    def test_ai_opponent_returns_none_for_spectator(self):
        """An AI opponent (no 'user' key) returns None if username doesn't match."""
        data = make_lichess_game_json()
        data["players"]["black"] = {"aiLevel": 3}  # no user key
        game = ChessGame.from_lichess_json(data, "SomeoneElse")
        assert game is None
