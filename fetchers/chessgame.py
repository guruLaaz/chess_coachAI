# chessgame.py

import datetime

class ChessGame:
    def __init__(self, white, black, end_time, termination, white_result, black_result,
                 my_color=None, my_clock_left=0, opponent_clock_left=0):
        self.white = white
        self.black = black
        self.end_time = end_time  # datetime object
        self.termination = termination
        self.white_result = white_result
        self.black_result = black_result
        self.my_color = my_color
        self.my_clock_left = my_clock_left
        self.opponent_clock_left = opponent_clock_left

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
            # Cannot determine color, skip this game
            return None

        # Parse end_time
        end_time_unix = data.get('end_time')  # may be int or None
        end_time = datetime.datetime.fromtimestamp(end_time_unix) if end_time_unix else datetime.datetime.now()

        # Clock info (default to 0 if not present)
        my_clock = 0
        opp_clock = 0
        # Attempt to get from pgn clock info (optional)
        # Could be expanded later if needed

        return cls(
            white=data.get('white', {}).get('username', ''),
            black=data.get('black', {}).get('username', ''),
            end_time=end_time,
            termination=data.get('termination', ''),
            white_result=data.get('white', {}).get('result', ''),
            black_result=data.get('black', {}).get('result', ''),
            my_color=my_color,
            my_clock_left=my_clock,
            opponent_clock_left=opp_clock
        )
