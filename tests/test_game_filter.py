import datetime
from unittest.mock import patch
from game_filter import filter_games_by_days
from helpers import make_chess_game


class TestFilterGamesByDays:
    _fixed_now = datetime.datetime(2025, 6, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)

    @patch("game_filter.datetime")
    def test_filters_old_games(self, mock_dt):
        mock_dt.now.return_value = self._fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)

        old_game = make_chess_game(end_time=datetime.datetime(2025, 5, 1))
        recent_game = make_chess_game(end_time=datetime.datetime(2025, 6, 19))

        result = filter_games_by_days([old_game, recent_game], days=7)
        assert len(result) == 1
        assert result[0] is recent_game

    @patch("game_filter.datetime")
    def test_keeps_games_within_range(self, mock_dt):
        mock_dt.now.return_value = self._fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)

        g1 = make_chess_game(end_time=datetime.datetime(2025, 6, 18))
        g2 = make_chess_game(end_time=datetime.datetime(2025, 6, 20))

        result = filter_games_by_days([g1, g2], days=30)
        assert len(result) == 2

    def test_days_zero_returns_all(self):
        games = [make_chess_game(), make_chess_game()]
        result = filter_games_by_days(games, days=0)
        assert len(result) == 2

    def test_days_negative_returns_all(self):
        games = [make_chess_game()]
        result = filter_games_by_days(games, days=-5)
        assert len(result) == 1

    def test_empty_list(self):
        result = filter_games_by_days([], days=7)
        assert result == []
