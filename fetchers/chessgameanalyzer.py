# chessgameanalyzer.py


class ChessGameAnalyzer:
    def __init__(self, my_username, games):
        self.my_username = my_username.lower()
        self.games = games

    def summarize(self):
        total = len(self.games)
        if total == 0:
            return {}

        wins = 0
        losses = 0
        draws = 0
        wins_white = 0
        wins_black = 0
        games_white = 0
        games_black = 0

        for g in self.games:
            my_result = g.white_result.lower() if g.my_color == 'white' else g.black_result.lower()

            if g.my_color == 'white':
                games_white += 1
            else:
                games_black += 1

            if my_result == 'win':
                wins += 1
                if g.my_color == 'white':
                    wins_white += 1
                else:
                    wins_black += 1
            elif my_result in ('checkmated', 'timeout', 'resigned',
                               'abandoned', 'lose'):
                losses += 1
            else:
                draws += 1

        stats = {}
        stats['total_games'] = total
        stats['wins'] = wins
        stats['losses'] = losses
        stats['draws'] = draws
        stats['games_white'] = games_white
        stats['games_black'] = games_black

        stats['win_percent'] = round(100 * wins / total, 2)
        stats['win_white_percent'] = round(100 * wins_white / games_white, 2) if games_white else 0
        stats['win_black_percent'] = round(100 * wins_black / games_black, 2) if games_black else 0

        return stats
