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
