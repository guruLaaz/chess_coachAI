import datetime

import chess

from chessgame import ChessGame
from chesscom_fetcher import ChessCom_Fetcher
from repertoire_analyzer import OpeningEvaluation


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


async def fetch_all_archives(fetcher: ChessCom_Fetcher, username: str):
    """Fetch all monthly archive JSONs for a Chess.com user (test helper)."""
    archives = await fetcher.get_archives(username)
    results = []
    for url in archives:
        month_data = await fetcher.fetch_games_by_month(url)
        results.append(month_data)
    return results


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


def make_eval(eco_code="B90", eco_name="Sicilian", my_color="white",
              deviation_ply=6, deviating_side="white", eval_cp=-50,
              is_fully_booked=False, fen=None, best_move="d2d4",
              played_move="g1f3", book_moves=None, eval_loss_cp=50,
              game_moves_uci=None, my_result="win", time_class="blitz",
              game_url="https://www.chess.com/game/live/12345"):
    """Build an OpeningEvaluation with coaching data for testing."""
    if fen is None:
        fen = chess.Board().fen()
    return OpeningEvaluation(
        eco_code=eco_code,
        eco_name=eco_name,
        my_color=my_color,
        deviation_ply=deviation_ply,
        deviating_side=deviating_side,
        eval_cp=eval_cp,
        is_fully_booked=is_fully_booked,
        fen_at_deviation=fen,
        best_move_uci=best_move,
        played_move_uci=played_move,
        book_moves_uci=book_moves if book_moves is not None else [best_move, played_move],
        eval_loss_cp=eval_loss_cp,
        game_moves_uci=game_moves_uci or [],
        my_result=my_result,
        time_class=time_class,
        game_url=game_url,
    )


def starting_fen():
    """Return the standard starting position FEN."""
    return chess.Board().fen()


def fen_after_moves(*uci_moves):
    """Return the FEN after playing the given UCI moves from the start."""
    board = chess.Board()
    for m in uci_moves:
        board.push(chess.Move.from_uci(m))
    return board.fen()
