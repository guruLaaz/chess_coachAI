import datetime
from chessgame import ChessGame


def make_game_json(white_user="PlayerA", black_user="PlayerB",
                   white_result="win", black_result="lose",
                   end_time=None, pgn=None, eco_url="", time_class=None,
                   game_url=""):
    """Build a raw Chess.com game JSON dict for testing."""
    if end_time is None:
        end_time = int(datetime.datetime(2025, 6, 15, 12, 0, 0).timestamp())
    data = {
        "white": {"username": white_user, "result": white_result},
        "black": {"username": black_user, "result": black_result},
        "end_time": end_time,
    }
    if pgn is not None:
        data["pgn"] = pgn
    if eco_url:
        data["eco"] = eco_url
    if time_class is not None:
        data["time_class"] = time_class
    if game_url:
        data["url"] = game_url
    return data


def make_archive_response(games_data):
    """Build a Chess.com monthly archive API response."""
    return {"games": games_data}


def make_lichess_game_json(white_user="PlayerA", black_user="PlayerB",
                           winner=None, status="resign",
                           last_move_at=None, pgn=None,
                           speed="blitz", game_id="abc12345",
                           eco="B90", opening_name="Sicilian Defense"):
    """Build a raw Lichess game JSON dict for testing."""
    if last_move_at is None:
        last_move_at = int(datetime.datetime(2025, 6, 15, 12, 0, 0).timestamp() * 1000)
    data = {
        "id": game_id,
        "speed": speed,
        "status": status,
        "players": {
            "white": {"user": {"name": white_user}},
            "black": {"user": {"name": black_user}},
        },
        "lastMoveAt": last_move_at,
        "createdAt": last_move_at - 600000,
    }
    if winner is not None:
        data["winner"] = winner
    if pgn is not None:
        data["pgn"] = pgn
    if eco or opening_name:
        data["opening"] = {}
        if eco:
            data["opening"]["eco"] = eco
        if opening_name:
            data["opening"]["name"] = opening_name
    return data


def make_chess_game(my_color="white", white_result="win", black_result="lose",
                    end_time=None, pgn=None, eco_code=None, eco_name=None,
                    time_class="blitz", game_url=""):
    """Build a ChessGame object directly for analyzer/filter tests."""
    if end_time is None:
        end_time = datetime.datetime(2025, 6, 15, 12, 0, 0)
    return ChessGame(
        white="PlayerA",
        black="PlayerB",
        end_time=end_time,
        white_result=white_result,
        black_result=black_result,
        my_color=my_color,
        pgn=pgn,
        eco_code=eco_code,
        eco_name=eco_name,
        time_class=time_class,
        game_url=game_url,
    )
