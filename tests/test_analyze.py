"""Tests for analyze.py utility functions."""
import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyze import (_is_current_month, fetch_games, fetch_lichess_games,
                     fetch_all_sources, run_analysis, main)
from helpers import make_game_json, make_chess_game, make_lichess_game_json


class TestIsCurrentMonth:
    def test_current_month_returns_true(self):
        now = datetime.now(timezone.utc)
        url = f"https://api.chess.com/pub/player/x/games/{now.year}/{now.month:02d}"
        assert _is_current_month(url) is True

    def test_past_month_returns_false(self):
        url = "https://api.chess.com/pub/player/x/games/2020/01"
        assert _is_current_month(url) is False

    def test_past_year_returns_false(self):
        url = "https://api.chess.com/pub/player/x/games/2019/12"
        assert _is_current_month(url) is False

    def test_far_future_returns_false(self):
        url = "https://api.chess.com/pub/player/x/games/2099/01"
        assert _is_current_month(url) is False

    def test_unparseable_url_returns_true(self):
        """Unparseable URLs are treated as current (always refresh)."""
        assert _is_current_month("https://api.chess.com/something/weird") is True

    def test_empty_url_returns_true(self):
        assert _is_current_month("") is True


class TestFetchGamesForceRefresh:
    """Tests for fetch_games with force_refresh (--no-cache behavior)."""

    @pytest.mark.asyncio
    async def test_force_refresh_skips_cache_reads(self):
        """With force_refresh=True, cache.get_archive is never called."""
        mock_cache = MagicMock()
        mock_cache.get_archive = MagicMock()
        mock_cache.save_archive = MagicMock()

        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.get_archives = AsyncMock(return_value=[
                "https://api.chess.com/pub/player/bob/games/2020/01"
            ])
            instance.fetch_games_by_month = AsyncMock(return_value={"games": []})

            await fetch_games("bob", 0, cache=mock_cache, force_refresh=True)

            # Cache read should NOT have been called
            mock_cache.get_archive.assert_not_called()
            # But cache write SHOULD have been called
            mock_cache.save_archive.assert_called_once()

    @pytest.mark.asyncio
    async def test_normal_mode_reads_cache(self):
        """Without force_refresh, cache.get_archive IS called."""
        mock_cache = MagicMock()
        mock_cache.get_archive = MagicMock(return_value={"games": []})
        mock_cache.save_archive = MagicMock()

        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.get_archives = AsyncMock(return_value=[
                "https://api.chess.com/pub/player/bob/games/2020/01"
            ])
            instance.fetch_games_by_month = AsyncMock(return_value={"games": []})

            await fetch_games("bob", 0, cache=mock_cache, force_refresh=False)

            # Cache read SHOULD have been called
            mock_cache.get_archive.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_refresh_still_saves_to_cache(self):
        """force_refresh fetches from API but saves results to cache."""
        mock_cache = MagicMock()
        mock_cache.save_archive = MagicMock()

        month_data = {"games": [{"url": "g1"}]}

        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.get_archives = AsyncMock(return_value=[
                "https://api.chess.com/pub/player/bob/games/2020/01",
                "https://api.chess.com/pub/player/bob/games/2020/02",
            ])
            instance.fetch_games_by_month = AsyncMock(return_value=month_data)

            await fetch_games("bob", 0, cache=mock_cache, force_refresh=True)

            # Both months should be saved to cache
            assert mock_cache.save_archive.call_count == 2


class TestFetchGamesNetworkErrors:
    """Tests for network error handling in fetch_games."""

    @pytest.mark.asyncio
    async def test_archive_fetch_error_exits(self):
        """If get_archives fails (DNS error, etc.), sys.exit(1) is called."""
        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.get_archives = AsyncMock(
                side_effect=Exception("DNS resolution failed"))

            with pytest.raises(SystemExit) as exc_info:
                await fetch_games("bob", 0)

            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_month_fetch_error_continues(self):
        """If a single month fails, it's skipped and others continue."""
        call_count = 0

        async def mock_fetch(url):
            nonlocal call_count
            call_count += 1
            if "2020/01" in url:
                raise Exception("Connection timeout")
            return {"games": [{"url": "g1"}]}

        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.get_archives = AsyncMock(return_value=[
                "https://api.chess.com/pub/player/bob/games/2020/01",
                "https://api.chess.com/pub/player/bob/games/2020/02",
            ])
            instance.fetch_games_by_month = mock_fetch

            games = await fetch_games("bob", 0)

            # Should have attempted both months
            assert call_count == 2
            # Should not crash — returned games from the successful month

    @pytest.mark.asyncio
    async def test_all_months_fail_returns_empty(self):
        """If all months fail, returns empty list (no crash)."""
        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.get_archives = AsyncMock(return_value=[
                "https://api.chess.com/pub/player/bob/games/2020/01",
            ])
            instance.fetch_games_by_month = AsyncMock(
                side_effect=Exception("Network error"))

            games = await fetch_games("bob", 0)
            assert games == []


class TestFetchGamesFilters:
    """Tests for days and time-control filter branches in fetch_games."""

    def _make_fetcher_with_game(self, username="bob", time_class="blitz"):
        """Helper: patch ChessCom_Fetcher to return one parseable game."""
        game_json = make_game_json(
            white_user=username, black_user="opp",
            white_result="win", black_result="lose",
            time_class=time_class,
            game_url="https://www.chess.com/game/live/111",
        )
        return {
            "get_archives": AsyncMock(return_value=[
                "https://api.chess.com/pub/player/bob/games/2020/01"
            ]),
            "fetch_games_by_month": AsyncMock(return_value={"games": [game_json]}),
        }

    @pytest.mark.asyncio
    async def test_days_filter_applied(self):
        """When days > 0 the days filter branch runs."""
        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            mocks = self._make_fetcher_with_game()
            instance = MockFetcher.return_value
            instance.get_archives = mocks["get_archives"]
            instance.fetch_games_by_month = mocks["fetch_games_by_month"]

            # days=30: the filter runs (game is old, so filtered out)
            games = await fetch_games("bob", 30)
            assert isinstance(games, list)

    @pytest.mark.asyncio
    async def test_include_tc_filter_applied(self):
        """include_tc filters to matching time controls only."""
        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            mocks = self._make_fetcher_with_game(time_class="blitz")
            instance = MockFetcher.return_value
            instance.get_archives = mocks["get_archives"]
            instance.fetch_games_by_month = mocks["fetch_games_by_month"]

            games = await fetch_games("bob", 0, include_tc={"blitz"})
            assert len(games) == 1

    @pytest.mark.asyncio
    async def test_exclude_tc_filter_applied(self):
        """exclude_tc removes matching time controls."""
        with patch("analyze.ChessCom_Fetcher") as MockFetcher:
            mocks = self._make_fetcher_with_game(time_class="bullet")
            instance = MockFetcher.return_value
            instance.get_archives = mocks["get_archives"]
            instance.fetch_games_by_month = mocks["fetch_games_by_month"]

            games = await fetch_games("bob", 0, exclude_tc={"bullet"})
            assert len(games) == 0


def _make_mock_eval(fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    game_url="https://chess.com/game/1"):
    """Create a mock OpeningEvaluation for run_analysis tests."""
    ev = MagicMock()
    ev.eco_code = "B90"
    ev.eco_name = "Sicilian"
    ev.my_color = "white"
    ev.deviation_ply = 6
    ev.deviating_side = "white"
    ev.eval_cp = 50
    ev.is_fully_booked = False
    ev.fen_at_deviation = fen
    ev.best_move_uci = "d2d4"
    ev.played_move_uci = "g1f3"
    ev.book_moves_uci = ["e2e4"]
    ev.eval_loss_cp = 30
    ev.game_moves_uci = []
    ev.game_url = game_url
    ev.times_played = 1
    return ev


def _make_opening_stats():
    """Create a mock OpeningStats for run_analysis tests."""
    stats = MagicMock()
    stats.eco_code = "B90"
    stats.eco_name = "Sicilian"
    stats.color = "white"
    stats.times_played = 2
    stats.avg_eval = 50
    stats.avg_deviation_ply = 6
    return stats


class TestRunAnalysis:
    """Tests for run_analysis() orchestration logic."""

    def _make_game(self):
        return make_chess_game(
            pgn='[Event "Live"]\n1. e4 c5 2. Nf3 d6 *',
            eco_code="B90", eco_name="Sicilian",
            game_url="https://chess.com/game/1",
        )

    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_prints_stats(self, MockAnalyzer, MockDetector, MockEvaluator):
        """run_analysis prints stats when summarize returns data."""
        MockAnalyzer.return_value.summarize.return_value = {
            "total_games": 10, "wins": 5, "losses": 3, "draws": 2,
            "win_percent": 50, "win_white_percent": 60, "win_black_percent": 40,
            "games_white": 5, "games_black": 5,
        }
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)

        rep = MagicMock()
        rep.analyze_repertoire.return_value = ({}, [])
        with patch("analyze.RepertoireAnalyzer", return_value=rep):
            result = run_analysis([self._make_game()], "bob", "sf", "book", 18)

        assert result is None  # no openings found, report=False

    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_all_cached_skips_engine(self, MockAnalyzer, MockDetector, MockEvaluator):
        """When all games are cached, StockfishEvaluator is not used."""
        MockAnalyzer.return_value.summarize.return_value = None
        mock_cache = MagicMock()
        game = self._make_game()
        ev = _make_mock_eval(game_url=game.game_url)
        mock_cache.get_cached_evaluations.return_value = {game.game_url: ev}

        with patch("analyze.RepertoireAnalyzer") as MockRep:
            run_analysis([game], "bob", "sf", "book", 18, cache=mock_cache)

        # Engine context manager should NOT have been entered
        MockEvaluator.return_value.__enter__.assert_not_called()

    @patch("analyze.RepertoireAnalyzer")
    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_uncached_runs_engine(self, MockAnalyzer, MockDetector,
                                  MockEvaluator, MockRep):
        """When cache is empty, engine analysis runs."""
        MockAnalyzer.return_value.summarize.return_value = None
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)
        MockRep.return_value.analyze_repertoire.return_value = ({}, [])

        mock_cache = MagicMock()
        mock_cache.get_cached_evaluations.return_value = {}

        run_analysis([self._make_game()], "bob", "sf", "book", 18, cache=mock_cache)

        MockEvaluator.return_value.__enter__.assert_called_once()

    @patch("analyze.RepertoireAnalyzer")
    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_no_cache_runs_engine(self, MockAnalyzer, MockDetector,
                                  MockEvaluator, MockRep):
        """When cache=None, engine analysis runs."""
        MockAnalyzer.return_value.summarize.return_value = None
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)
        MockRep.return_value.analyze_repertoire.return_value = ({}, [])

        run_analysis([self._make_game()], "bob", "sf", "book", 18, cache=None)

        MockEvaluator.return_value.__enter__.assert_called_once()

    @patch("analyze.RepertoireAnalyzer")
    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_empty_stats_returns_none(self, MockAnalyzer, MockDetector,
                                      MockEvaluator, MockRep):
        """No openings detected → returns None when report=False."""
        MockAnalyzer.return_value.summarize.return_value = None
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)
        MockRep.return_value.analyze_repertoire.return_value = ({}, [])

        result = run_analysis([self._make_game()], "bob", "sf", "book", 18, report=False)
        assert result is None

    @patch("analyze.RepertoireAnalyzer")
    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_empty_stats_returns_empty_list_for_report(self, MockAnalyzer, MockDetector,
                                                        MockEvaluator, MockRep):
        """No openings detected → returns [] when report=True."""
        MockAnalyzer.return_value.summarize.return_value = None
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)
        MockRep.return_value.analyze_repertoire.return_value = ({}, [])

        result = run_analysis([self._make_game()], "bob", "sf", "book", 18, report=True)
        assert result == []

    @patch("analyze.RepertoireAnalyzer")
    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_report_returns_all_evals(self, MockAnalyzer, MockDetector,
                                      MockEvaluator, MockRep):
        """report=True returns evaluation list when openings found."""
        MockAnalyzer.return_value.summarize.return_value = None
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)

        game = self._make_game()
        ev = _make_mock_eval()
        stats_key = "Sicilian_white"
        opening_stats = {stats_key: _make_opening_stats()}
        MockRep.return_value.analyze_repertoire.return_value = (
            opening_stats, [(game, ev)])

        result = run_analysis([game], "bob", "sf", "book", 18, report=True)
        assert len(result) == 1
        assert result[0] is ev

    @patch("analyze.RepertoireAnalyzer")
    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_new_evals_saved_to_cache(self, MockAnalyzer, MockDetector,
                                      MockEvaluator, MockRep):
        """Newly computed evaluations are saved to cache."""
        MockAnalyzer.return_value.summarize.return_value = None
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)

        game = self._make_game()
        ev = _make_mock_eval()
        opening_stats = {"Sicilian_white": _make_opening_stats()}
        MockRep.return_value.analyze_repertoire.return_value = (
            opening_stats, [(game, ev)])

        mock_cache = MagicMock()
        mock_cache.get_cached_evaluations.return_value = {}

        run_analysis([game], "bob", "sf", "book", 18, cache=mock_cache)

        mock_cache.save_evaluations_batch.assert_called_once()

    @patch("analyze.StockfishEvaluator")
    @patch("analyze.OpeningDetector")
    @patch("analyze.ChessGameAnalyzer")
    def test_force_refresh_skips_cache_read(self, MockAnalyzer, MockDetector,
                                            MockEvaluator):
        """force_refresh=True skips cache.get_cached_evaluations."""
        MockAnalyzer.return_value.summarize.return_value = None
        evaluator_ctx = MagicMock()
        MockEvaluator.return_value.__enter__ = MagicMock(return_value=evaluator_ctx)
        MockEvaluator.return_value.__exit__ = MagicMock(return_value=False)

        mock_cache = MagicMock()

        with patch("analyze.RepertoireAnalyzer") as MockRep:
            MockRep.return_value.analyze_repertoire.return_value = ({}, [])
            run_analysis([self._make_game()], "bob", "sf", "book", 18,
                         cache=mock_cache, force_refresh=True)

        mock_cache.get_cached_evaluations.assert_not_called()


class TestMain:
    """Tests for main() CLI entry point."""

    def _make_args(self, **overrides):
        args = MagicMock()
        args.chesscom_user = "bob"
        args.lichess_user = ""
        args.days = 0
        args.depth = 18
        args.stockfish = "/path/to/stockfish"
        args.book = "/path/to/book.bin"
        args.workers = 1
        args.no_cache = False
        args.report = False
        args.min_times = 1
        args.include = None
        args.exclude = None
        for k, v in overrides.items():
            setattr(args, k, v)
        return args

    @patch("analyze.argparse.ArgumentParser")
    @patch("analyze.os.path.isfile")
    def test_missing_stockfish_exits(self, mock_isfile, MockParser):
        """Missing stockfish binary causes sys.exit(1)."""
        MockParser.return_value.parse_args.return_value = self._make_args()
        mock_isfile.return_value = False  # stockfish not found

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch("analyze.argparse.ArgumentParser")
    @patch("analyze.os.path.isfile")
    def test_missing_book_exits(self, mock_isfile, MockParser):
        """Missing opening book causes sys.exit(1)."""
        MockParser.return_value.parse_args.return_value = self._make_args()
        # stockfish exists, but book does not
        mock_isfile.side_effect = lambda p: p == "/path/to/stockfish"

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch("analyze.run_analysis")
    @patch("analyze.asyncio.run")
    @patch("analyze.GameCache")
    @patch("analyze.os.makedirs")
    @patch("analyze.argparse.ArgumentParser")
    @patch("analyze.os.path.isfile", return_value=True)
    def test_no_games_exits_zero(self, mock_isfile, MockParser, mock_makedirs,
                                  MockCache, mock_asyncio_run, mock_run_analysis):
        """No games found → sys.exit(0)."""
        MockParser.return_value.parse_args.return_value = self._make_args()
        mock_asyncio_run.return_value = []  # no games

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @patch("analyze.EndgameClassifier")
    @patch("analyze.run_analysis")
    @patch("analyze.asyncio.run")
    @patch("analyze.GameCache")
    @patch("analyze.os.makedirs")
    @patch("analyze.argparse.ArgumentParser")
    @patch("analyze.os.path.isfile", return_value=True)
    def test_report_launches_generator(self, mock_isfile, MockParser, mock_makedirs,
                                        MockCache, mock_asyncio_run, mock_run_analysis,
                                        MockEndgame):
        """--report flag creates and runs CoachingReportGenerator."""
        MockEndgame.aggregate.return_value = []
        MockParser.return_value.parse_args.return_value = self._make_args(report=True)
        game = self._make_args()  # just needs to be truthy
        mock_asyncio_run.return_value = [game]
        ev = _make_mock_eval()
        mock_run_analysis.return_value = [ev]

        with patch("analyze.CoachingReportGenerator", create=True) as MockGen:
            # Patch the import inside main()
            with patch.dict("sys.modules", {"report_generator": MagicMock()}):
                with patch("builtins.__import__", side_effect=__builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__):
                    # Simpler: just patch at module level after import
                    pass

        # Actually, the import is local: "from report_generator import CoachingReportGenerator"
        # We need to patch it differently. Let's use a mock module.
        with patch("analyze.run_analysis") as mock_ra:
            mock_ra.return_value = [ev]
            with patch.dict("sys.modules", {
                "report_generator": MagicMock(
                    CoachingReportGenerator=MagicMock()
                )
            }):
                mock_asyncio_run.return_value = [game]
                main()
                # Verify the generator was created
                report_mod = sys.modules["report_generator"]
                report_mod.CoachingReportGenerator.assert_called_once()
                report_mod.CoachingReportGenerator.return_value.run.assert_called_once()

    @patch("analyze.EndgameClassifier")
    @patch("analyze.run_analysis")
    @patch("analyze.asyncio.run")
    @patch("analyze.GameCache")
    @patch("analyze.os.makedirs")
    @patch("analyze.argparse.ArgumentParser")
    @patch("analyze.os.path.isfile", return_value=True)
    def test_cache_closed_on_success(self, mock_isfile, MockParser, mock_makedirs,
                                      MockCache, mock_asyncio_run, mock_run_analysis,
                                      MockEndgame):
        """cache.close() is called on successful execution."""
        MockEndgame.aggregate.return_value = []
        MockParser.return_value.parse_args.return_value = self._make_args()
        mock_asyncio_run.return_value = [MagicMock()]
        mock_run_analysis.return_value = None

        main()

        MockCache.return_value.close.assert_called_once()

    @patch("analyze.EndgameClassifier")
    @patch("analyze.run_analysis")
    @patch("analyze.asyncio.run")
    @patch("analyze.GameCache")
    @patch("analyze.os.makedirs")
    @patch("analyze.argparse.ArgumentParser")
    @patch("analyze.os.path.isfile", return_value=True)
    def test_cache_closed_on_error(self, mock_isfile, MockParser, mock_makedirs,
                                    MockCache, mock_asyncio_run, mock_run_analysis,
                                    MockEndgame):
        """cache.close() is called even when an error occurs."""
        MockEndgame.aggregate.return_value = []
        MockParser.return_value.parse_args.return_value = self._make_args()
        mock_asyncio_run.return_value = [MagicMock()]
        mock_run_analysis.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            main()

        MockCache.return_value.close.assert_called_once()

    @patch("analyze.GameCache")
    @patch("analyze.os.makedirs")
    @patch("analyze.argparse.ArgumentParser")
    @patch("analyze.os.path.isfile", return_value=True)
    def test_no_users_provided_exits_with_error(self, mock_isfile, MockParser,
                                                  mock_makedirs, MockCache):
        """Both users empty → parser.error is called."""
        args = self._make_args(chesscom_user="", lichess_user="")
        MockParser.return_value.parse_args.return_value = args

        # parser.error() raises SystemExit(2) by default
        MockParser.return_value.error.side_effect = SystemExit(2)

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
        MockParser.return_value.error.assert_called_once()


class TestFetchLichessGames:
    """Tests for fetch_lichess_games()."""

    @pytest.mark.asyncio
    async def test_fetches_and_parses_lichess_games(self):
        lichess_game = make_lichess_game_json(
            white_user="alice", black_user="bob",
            winner="white", speed="blitz", game_id="test123",
        )
        with patch("analyze.LichessFetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.fetch_games = AsyncMock(return_value=[lichess_game])
            games = await fetch_lichess_games("alice", 0)
        assert len(games) == 1
        assert games[0].game_url == "https://lichess.org/test123"
        assert games[0].time_class == "blitz"

    @pytest.mark.asyncio
    async def test_lichess_api_error_exits(self):
        with patch("analyze.LichessFetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.fetch_games = AsyncMock(side_effect=Exception("Network error"))
            with pytest.raises(SystemExit) as exc_info:
                await fetch_lichess_games("alice", 0)
            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_days_filter_computes_since(self):
        with patch("analyze.LichessFetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.fetch_games = AsyncMock(return_value=[])
            await fetch_lichess_games("alice", 30)
            call_args = instance.fetch_games.call_args
            assert call_args[1].get("since") is not None

    @pytest.mark.asyncio
    async def test_include_tc_filter_applied(self):
        lichess_game = make_lichess_game_json(
            white_user="alice", black_user="bob",
            winner="white", speed="rapid", game_id="r1",
        )
        with patch("analyze.LichessFetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.fetch_games = AsyncMock(return_value=[lichess_game])
            games = await fetch_lichess_games("alice", 0, include_tc={"rapid"})
        assert len(games) == 1

    @pytest.mark.asyncio
    async def test_exclude_tc_filter_applied(self):
        lichess_game = make_lichess_game_json(
            white_user="alice", black_user="bob",
            winner="white", speed="bullet", game_id="b1",
        )
        with patch("analyze.LichessFetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.fetch_games = AsyncMock(return_value=[lichess_game])
            games = await fetch_lichess_games("alice", 0, exclude_tc={"bullet"})
        assert len(games) == 0

    @pytest.mark.asyncio
    async def test_days_zero_sends_no_since(self):
        """When days=0, since param is not sent to Lichess API."""
        with patch("analyze.LichessFetcher") as MockFetcher:
            instance = MockFetcher.return_value
            instance.fetch_games = AsyncMock(return_value=[])
            await fetch_lichess_games("alice", 0)
            call_args = instance.fetch_games.call_args
            assert call_args[1].get("since") is None


class TestFetchAllSources:
    """Tests for fetch_all_sources() merging both platforms."""

    @pytest.mark.asyncio
    async def test_chesscom_only(self):
        with patch("analyze.fetch_games", new_callable=AsyncMock) as mock_cc:
            mock_cc.return_value = [MagicMock(game_url="cc1")]
            games = await fetch_all_sources("bob", "", 0)
        assert len(games) == 1
        mock_cc.assert_called_once()

    @pytest.mark.asyncio
    async def test_lichess_only(self):
        with patch("analyze.fetch_lichess_games", new_callable=AsyncMock) as mock_li:
            mock_li.return_value = [MagicMock(game_url="li1")]
            games = await fetch_all_sources("", "alice", 0)
        assert len(games) == 1
        mock_li.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_sources_merged(self):
        with patch("analyze.fetch_games", new_callable=AsyncMock) as mock_cc, \
             patch("analyze.fetch_lichess_games", new_callable=AsyncMock) as mock_li:
            mock_cc.return_value = [MagicMock(game_url="cc1")]
            mock_li.return_value = [MagicMock(game_url="li1")]
            games = await fetch_all_sources("bob", "alice", 0)
        assert len(games) == 2
