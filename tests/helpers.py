import datetime
from chessgame import ChessGame


def make_game_json(white_user="PlayerA", black_user="PlayerB",
                   white_result="win", black_result="lose",
                   termination="checkmate", end_time=None):
    """Build a raw Chess.com game JSON dict for testing."""
    if end_time is None:
        end_time = int(datetime.datetime(2025, 6, 15, 12, 0, 0).timestamp())
    return {
        "white": {"username": white_user, "result": white_result},
        "black": {"username": black_user, "result": black_result},
        "end_time": end_time,
        "termination": termination,
    }


def make_archive_response(games_data):
    """Build a Chess.com monthly archive API response."""
    return {"games": games_data}


def make_chess_game(my_color="white", white_result="win", black_result="lose",
                    termination="checkmate", end_time=None):
    """Build a ChessGame object directly for analyzer/filter tests."""
    if end_time is None:
        end_time = datetime.datetime(2025, 6, 15, 12, 0, 0)
    return ChessGame(
        white="PlayerA",
        black="PlayerB",
        end_time=end_time,
        termination=termination,
        white_result=white_result,
        black_result=black_result,
        my_color=my_color,
    )
