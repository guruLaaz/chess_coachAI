# chessgame.py

import datetime
import re


class ChessGame:
    def __init__(self, white, black, end_time, white_result, black_result,
                 my_color=None, my_clock_left=0, opponent_clock_left=0,
                 pgn=None, eco_code=None, eco_name=None, eco_url=None,
                 time_class=None, game_url=""):
        self.white = white
        self.black = black
        self.end_time = end_time  # datetime object
        self.white_result = white_result
        self.black_result = black_result
        self.my_color = my_color
        self.my_clock_left = my_clock_left
        self.opponent_clock_left = opponent_clock_left
        self.pgn = pgn
        self.eco_code = eco_code
        self.eco_name = eco_name
        self.eco_url = eco_url
        self.time_class = time_class  # "bullet", "blitz", "rapid", "daily"
        self.game_url = game_url      # Chess.com game URL (unique ID)

    @classmethod
    def from_json(cls, data, my_username):
        my_username_lower = my_username.lower()

        # Determine my color
        white_user = data.get('white', {}).get('username', '').lower()
        black_user = data.get('black', {}).get('username', '').lower()

        if my_username_lower == white_user:
            my_color = 'white'
        elif my_username_lower == black_user:
            my_color = 'black'
        else:
            return None

        # Parse end_time
        end_time_unix = data.get('end_time')
        end_time = datetime.datetime.fromtimestamp(end_time_unix) if end_time_unix else datetime.datetime.now()

        # Clock info (default to 0 if not present)
        my_clock = 0
        opp_clock = 0

        # PGN and ECO data
        pgn = data.get('pgn')

        eco_url = data.get('eco', '')
        eco_name = ''
        if '/openings/' in eco_url:
            eco_name = eco_url.split('/openings/')[-1].replace('-', ' ')

        eco_code = None
        if pgn:
            eco_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
            if eco_match:
                eco_code = eco_match.group(1)

        return cls(
            white=data.get('white', {}).get('username', ''),
            black=data.get('black', {}).get('username', ''),
            end_time=end_time,
            white_result=data.get('white', {}).get('result', ''),
            black_result=data.get('black', {}).get('result', ''),
            my_color=my_color,
            my_clock_left=my_clock,
            opponent_clock_left=opp_clock,
            pgn=pgn,
            eco_code=eco_code,
            eco_name=eco_name,
            eco_url=eco_url,
            time_class=data.get('time_class'),
            game_url=data.get('url', ''),
        )

    # Lichess speed -> our time_class
    _LICHESS_SPEED_MAP = {
        "bullet": "bullet",
        "blitz": "blitz",
        "rapid": "rapid",
        "classical": "rapid",
        "correspondence": "daily",
        "ultraBullet": "bullet",
    }

    @classmethod
    def from_lichess_json(cls, data, my_username):
        """Convert a Lichess API game JSON dict to a ChessGame.

        Returns None if my_username is not a participant.
        """
        my_username_lower = my_username.lower()

        players = data.get("players", {})
        white_info = players.get("white", {})
        black_info = players.get("black", {})

        white_name = white_info.get("user", {}).get("name", "").lower()
        black_name = black_info.get("user", {}).get("name", "").lower()

        if my_username_lower == white_name:
            my_color = "white"
        elif my_username_lower == black_name:
            my_color = "black"
        else:
            return None

        # Parse end_time from lastMoveAt (milliseconds)
        last_move_ms = data.get("lastMoveAt") or data.get("createdAt")
        if last_move_ms:
            end_time = datetime.datetime.fromtimestamp(last_move_ms / 1000)
        else:
            end_time = datetime.datetime.now()

        # Determine results from winner field
        winner = data.get("winner")
        status = data.get("status", "draw")

        if winner == "white":
            white_result = "win"
            black_result = "lose"
        elif winner == "black":
            white_result = "lose"
            black_result = "win"
        else:
            white_result = status
            black_result = status

        # PGN and opening data
        pgn = data.get("pgn")
        opening = data.get("opening", {})
        eco_code = opening.get("eco")
        eco_name = opening.get("name", "")

        # Time class mapping
        speed = data.get("speed", "")
        time_class = cls._LICHESS_SPEED_MAP.get(speed, speed)

        # Game URL
        game_id = data.get("id", "")
        game_url = f"https://lichess.org/{game_id}" if game_id else ""

        return cls(
            white=white_info.get("user", {}).get("name", ""),
            black=black_info.get("user", {}).get("name", ""),
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
