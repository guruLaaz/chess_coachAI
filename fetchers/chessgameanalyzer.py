# chessgameanalyzer.py

from collections import Counter

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

        termination_counter = Counter()

        for g in self.games:
            # Normalize results
            white_result = g.white_result.lower()
            black_result = g.black_result.lower()
            termination = g.termination.lower()

            if g.my_color == 'white':
                if white_result in ['win', 'checkmate']:
                    wins += 1
                    wins_white += 1
                    termination_counter[termination] += 1
                elif white_result in ['lose', 'checkmated', 'timeout']:
                    losses += 1
                else:
                    draws += 1

            elif g.my_color == 'black':
                if black_result in ['win', 'checkmate']:
                    wins += 1
                    wins_black += 1
                    termination_counter[termination] += 1
                elif black_result in ['lose', 'checkmated', 'timeout']:
                    losses += 1
                else:
                    draws += 1

        stats = {}
        stats['total_games'] = total
        stats['wins'] = wins
        stats['losses'] = losses
        stats['draws'] = draws

        stats['win_percent'] = round(100 * wins / total, 2)
        stats['win_white_percent'] = round(100 * wins_white / total, 2)
        stats['win_black_percent'] = round(100 * wins_black / total, 2)

        stats['checkmate_win_percent'] = round(
            100 * termination_counter.get('checkmate', 0) / wins, 2
        ) if wins > 0 else 0
        stats['time_win_percent'] = round(
            100 * termination_counter.get('time', 0) / wins, 2
        ) if wins > 0 else 0
        stats['abandon_win_percent'] = round(
            100 * termination_counter.get('abandon', 0) / wins, 2
        ) if wins > 0 else 0

        # Clock stats removed for rollback
        stats['avg_my_clock_on_checkmate_sec'] = 0
        stats['avg_opp_clock_on_my_time_loss_sec'] = 0

        return stats
