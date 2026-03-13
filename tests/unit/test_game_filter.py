import datetime
from unittest.mock import patch
from game_filter import filter_games_by_days, filter_games_by_time_class
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


class TestFilterGamesByTimeClass:
    def test_include_blitz_only(self):
        games = [
            make_chess_game(time_class="bullet"),
            make_chess_game(time_class="blitz"),
            make_chess_game(time_class="rapid"),
            make_chess_game(time_class="blitz"),
        ]
        result = filter_games_by_time_class(games, include={"blitz"})
        assert len(result) == 2
        assert all(g.time_class == "blitz" for g in result)

    def test_include_multiple_types(self):
        games = [
            make_chess_game(time_class="bullet"),
            make_chess_game(time_class="blitz"),
            make_chess_game(time_class="rapid"),
            make_chess_game(time_class="daily"),
        ]
        result = filter_games_by_time_class(games, include={"blitz", "rapid"})
        assert len(result) == 2

    def test_exclude_bullet(self):
        games = [
            make_chess_game(time_class="bullet"),
            make_chess_game(time_class="blitz"),
            make_chess_game(time_class="rapid"),
        ]
        result = filter_games_by_time_class(games, exclude={"bullet"})
        assert len(result) == 2
        assert all(g.time_class != "bullet" for g in result)

    def test_exclude_multiple_types(self):
        games = [
            make_chess_game(time_class="bullet"),
            make_chess_game(time_class="blitz"),
            make_chess_game(time_class="rapid"),
            make_chess_game(time_class="daily"),
        ]
        result = filter_games_by_time_class(games, exclude={"bullet", "daily"})
        assert len(result) == 2

    def test_include_takes_priority_over_exclude(self):
        games = [
            make_chess_game(time_class="bullet"),
            make_chess_game(time_class="blitz"),
            make_chess_game(time_class="rapid"),
        ]
        result = filter_games_by_time_class(games, include={"blitz"}, exclude={"blitz"})
        assert len(result) == 1
        assert result[0].time_class == "blitz"

    def test_no_filters_returns_all(self):
        games = [
            make_chess_game(time_class="bullet"),
            make_chess_game(time_class="blitz"),
        ]
        result = filter_games_by_time_class(games)
        assert len(result) == 2

    def test_include_nonexistent_type_returns_empty(self):
        games = [
            make_chess_game(time_class="bullet"),
            make_chess_game(time_class="blitz"),
        ]
        result = filter_games_by_time_class(games, include={"rapid"})
        assert len(result) == 0

    def test_empty_list(self):
        result = filter_games_by_time_class([], include={"blitz"})
        assert result == []

    def test_games_with_none_time_class(self):
        games = [
            make_chess_game(time_class=None),
            make_chess_game(time_class="blitz"),
        ]
        result = filter_games_by_time_class(games, include={"blitz"})
        assert len(result) == 1
        assert result[0].time_class == "blitz"

    def test_exclude_with_none_time_class(self):
        games = [
            make_chess_game(time_class=None),
            make_chess_game(time_class="blitz"),
        ]
        result = filter_games_by_time_class(games, exclude={"blitz"})
        assert len(result) == 1
        assert result[0].time_class is None
