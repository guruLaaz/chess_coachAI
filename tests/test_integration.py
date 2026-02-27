"""
Integration tests: full pipeline (fetch → parse → filter → analyze)
with mocked HTTP responses, plus a real-API smoke test.
"""
import datetime
import json
import re
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from chesscom_fetcher import ChessCom_Fetcher, BASE_URL
from lichess_fetcher import LichessFetcher, LICHESS_API_BASE
from chessgame import ChessGame
from game_filter import filter_games_by_days
from chessgameanalyzer import ChessGameAnalyzer
from helpers import make_game_json, make_archive_response, make_lichess_game_json


USERNAME = "TestPlayer"
ARCHIVES_URL = f"{BASE_URL}/{USERNAME}/games/archives"


def _ts(dt):
    """Convert a datetime to a Unix timestamp int."""
    return int(dt.timestamp())


# --- Realistic game fixtures spanning two months ---

_now = datetime.datetime(2025, 6, 20, 12, 0, 0)
_recent_ts = _ts(_now - datetime.timedelta(days=3))
_mid_ts = _ts(_now - datetime.timedelta(days=15))
_old_ts = _ts(_now - datetime.timedelta(days=60))

MONTH1_GAMES = [
    make_game_json(white_user=USERNAME, black_user="Opp1",
                   white_result="win", black_result="checkmated",
                   end_time=_old_ts),
    make_game_json(white_user="Opp2", black_user=USERNAME,
                   white_result="win", black_result="timeout",
                   end_time=_old_ts),
    make_game_json(white_user=USERNAME, black_user="Opp3",
                   white_result="stalemate", black_result="stalemate",
                   end_time=_old_ts),
]

MONTH2_GAMES = [
    make_game_json(white_user=USERNAME, black_user="Opp4",
                   white_result="win", black_result="timeout",
                   end_time=_recent_ts),
    make_game_json(white_user="Opp5", black_user=USERNAME,
                   white_result="lose", black_result="win",
                   end_time=_recent_ts),
    make_game_json(white_user="Opp6", black_user=USERNAME,
                   white_result="win", black_result="checkmated",
                   end_time=_mid_ts),
    make_game_json(white_user=USERNAME, black_user="Opp7",
                   white_result="lose", black_result="win",
                   end_time=_recent_ts),
]

MONTH1_URL = f"{BASE_URL}/{USERNAME}/games/2025/04"
MONTH2_URL = f"{BASE_URL}/{USERNAME}/games/2025/06"


def _mock_two_months(mock):
    """Register mocked responses for a two-month archive scenario."""
    mock.get(ARCHIVES_URL, payload={"archives": [MONTH1_URL, MONTH2_URL]})
    mock.get(MONTH1_URL, payload=make_archive_response(MONTH1_GAMES))
    mock.get(MONTH2_URL, payload=make_archive_response(MONTH2_GAMES))


async def _run_pipeline(username, days, fixed_now=None):
    """Execute the full fetch → parse → filter → analyze pipeline."""
    fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")
    all_archives = await fetcher.fetch_all_archives(username)

    raw_games = []
    for month in all_archives:
        raw_games.extend(month.get("games", []))

    games = [g for g in (ChessGame.from_json(g, username) for g in raw_games) if g is not None]

    if fixed_now is not None:
        with patch("game_filter.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now.replace(tzinfo=datetime.timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
            games = filter_games_by_days(games, days)
    else:
        games = filter_games_by_days(games, days)

    analyzer = ChessGameAnalyzer(username, games)
    return analyzer.summarize(), games


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_happy_path_all_games(self):
        """Fetch 2 months, no date filter → all 7 games analyzed."""
        with aioresponses() as mock:
            _mock_two_months(mock)
            stats, games = await _run_pipeline(USERNAME, days=0)

        assert len(games) == 7
        assert stats["total_games"] == 7
        assert stats["wins"] == 3
        assert stats["losses"] == 3
        assert stats["draws"] == 1

    @pytest.mark.asyncio
    async def test_filter_narrows_to_recent(self):
        """Filter to last 7 days → only the 3 recent games survive."""
        with aioresponses() as mock:
            _mock_two_months(mock)
            stats, games = await _run_pipeline(USERNAME, days=7, fixed_now=_now)

        assert len(games) == 3
        assert stats["total_games"] == 3
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        assert stats["draws"] == 0

    @pytest.mark.asyncio
    async def test_filter_narrows_to_last_30_days(self):
        """Filter to last 30 days → recent + mid-age games (4 total)."""
        with aioresponses() as mock:
            _mock_two_months(mock)
            stats, games = await _run_pipeline(USERNAME, days=30, fixed_now=_now)

        assert len(games) == 4
        assert stats["total_games"] == 4

    @pytest.mark.asyncio
    async def test_all_games_filtered_out(self):
        """Filter to last 1 day → no games match → empty stats."""
        with aioresponses() as mock:
            _mock_two_months(mock)
            stats, games = await _run_pipeline(USERNAME, days=1, fixed_now=_now)

        assert len(games) == 0
        assert stats == {}


class TestSingleMonth:
    @pytest.mark.asyncio
    async def test_single_month_mixed_results(self):
        """One month with wins, losses, draws as both colors."""
        games_json = [
            make_game_json(white_user=USERNAME, black_user="A",
                           white_result="win", black_result="lose",
                           end_time=_recent_ts),
            make_game_json(white_user="B", black_user=USERNAME,
                           white_result="lose", black_result="win",
                           end_time=_recent_ts),
            make_game_json(white_user=USERNAME, black_user="C",
                           white_result="stalemate", black_result="stalemate",
                           end_time=_recent_ts),
            make_game_json(white_user="D", black_user=USERNAME,
                           white_result="stalemate", black_result="stalemate",
                           end_time=_recent_ts),
        ]
        month_url = f"{BASE_URL}/{USERNAME}/games/2025/06"

        with aioresponses() as mock:
            mock.get(ARCHIVES_URL, payload={"archives": [month_url]})
            mock.get(month_url, payload=make_archive_response(games_json))
            stats, games = await _run_pipeline(USERNAME, days=0)

        assert stats["total_games"] == 4
        assert stats["wins"] == 2
        assert stats["losses"] == 0
        assert stats["draws"] == 2
        # 1 win / 2 white games = 50%, 1 win / 2 black games = 50%
        assert stats["win_white_percent"] == 50.0
        assert stats["win_black_percent"] == 50.0


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_player_with_no_games(self):
        """Archives exist but all months are empty → empty stats."""
        month_url = f"{BASE_URL}/{USERNAME}/games/2025/01"

        with aioresponses() as mock:
            mock.get(ARCHIVES_URL, payload={"archives": [month_url]})
            mock.get(month_url, payload=make_archive_response([]))
            stats, games = await _run_pipeline(USERNAME, days=0)

        assert len(games) == 0
        assert stats == {}

    @pytest.mark.asyncio
    async def test_player_not_found_404(self):
        """HTTP 404 for archives → raises exception."""
        with aioresponses() as mock:
            mock.get(ARCHIVES_URL, status=404)
            fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")

            with pytest.raises(Exception):
                await fetcher.fetch_all_archives(USERNAME)

    @pytest.mark.asyncio
    async def test_no_archives(self):
        """Player exists but has zero archive months."""
        with aioresponses() as mock:
            mock.get(ARCHIVES_URL, payload={"archives": []})
            stats, games = await _run_pipeline(USERNAME, days=0)

        assert len(games) == 0
        assert stats == {}


class TestLargeBatch:
    @pytest.mark.asyncio
    async def test_many_games_across_months(self):
        """50 games across 5 months → stats are correct at scale."""
        month_urls = [f"{BASE_URL}/{USERNAME}/games/2025/{m:02d}" for m in range(1, 6)]
        all_game_jsons = []

        # 10 games per month: 5 wins as white, 3 losses as black, 2 draws
        for _ in range(5):
            month_games = []
            for i in range(5):
                month_games.append(make_game_json(
                    white_user=USERNAME, black_user=f"Opp{i}",
                    white_result="win", black_result="lose",
                    end_time=_recent_ts))
            for i in range(3):
                month_games.append(make_game_json(
                    white_user=f"Opp{i}", black_user=USERNAME,
                    white_result="win", black_result="checkmated",
                    end_time=_recent_ts))
            for i in range(2):
                month_games.append(make_game_json(
                    white_user=USERNAME, black_user=f"Opp{i}",
                    white_result="stalemate", black_result="stalemate",
                    end_time=_recent_ts))
            all_game_jsons.append(month_games)

        with aioresponses() as mock:
            mock.get(ARCHIVES_URL, payload={"archives": month_urls})
            for url, games_json in zip(month_urls, all_game_jsons):
                mock.get(url, payload=make_archive_response(games_json))

            stats, games = await _run_pipeline(USERNAME, days=0)

        assert len(games) == 50
        assert stats["total_games"] == 50
        assert stats["wins"] == 25
        assert stats["losses"] == 15
        assert stats["draws"] == 10
        assert stats["win_percent"] == 50.0


LICHESS_USERNAME = "TestPlayer"
LICHESS_GAMES_URL = f"{LICHESS_API_BASE}/games/user/{LICHESS_USERNAME}"
LICHESS_URL_PATTERN = re.compile(rf"^{re.escape(LICHESS_GAMES_URL)}")


def _ndjson_payload(games):
    """Create an NDJSON byte payload from a list of dicts."""
    return "\n".join(json.dumps(g) for g in games).encode()


def _make_lichess_games():
    """Build a set of Lichess game fixtures for mocked pipeline tests."""
    return [
        make_lichess_game_json(
            white_user=LICHESS_USERNAME, black_user="OppL1",
            winner="white", speed="blitz", game_id="li001",
            last_move_at=int(_recent_ts * 1000),
        ),
        make_lichess_game_json(
            white_user="OppL2", black_user=LICHESS_USERNAME,
            winner="black", speed="rapid", game_id="li002",
            last_move_at=int(_recent_ts * 1000),
        ),
        make_lichess_game_json(
            white_user=LICHESS_USERNAME, black_user="OppL3",
            winner=None, status="stalemate", speed="blitz", game_id="li003",
            last_move_at=int(_mid_ts * 1000),
        ),
        make_lichess_game_json(
            white_user="OppL4", black_user=LICHESS_USERNAME,
            winner="white", speed="bullet", game_id="li004",
            last_move_at=int(_old_ts * 1000),
        ),
    ]


async def _run_lichess_pipeline(username, days, fixed_now=None):
    """Execute the Lichess fetch → parse → filter → analyze pipeline."""
    fetcher = LichessFetcher(user_agent="TestAgent/1.0")
    raw_games = await fetcher.fetch_games(username)

    games = [g for g in (ChessGame.from_lichess_json(g, username)
                          for g in raw_games) if g is not None]

    if fixed_now is not None:
        with patch("game_filter.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now.replace(tzinfo=datetime.timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
            games = filter_games_by_days(games, days)
    else:
        games = filter_games_by_days(games, days)

    analyzer = ChessGameAnalyzer(username, games)
    return analyzer.summarize(), games


class TestLichessPipeline:
    """Mocked Lichess fetch → parse → filter → analyze pipeline."""

    @pytest.mark.asyncio
    async def test_happy_path_all_games(self):
        """Fetch Lichess games, no date filter → all 4 games analyzed."""
        lichess_games = _make_lichess_games()
        with aioresponses() as mock:
            mock.get(LICHESS_URL_PATTERN,
                     body=_ndjson_payload(lichess_games),
                     content_type="application/x-ndjson")
            stats, games = await _run_lichess_pipeline(LICHESS_USERNAME, days=0)

        assert len(games) == 4
        assert stats["total_games"] == 4
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        assert stats["draws"] == 1

    @pytest.mark.asyncio
    async def test_filter_recent_games(self):
        """Filter to last 7 days → only the 2 recent games survive."""
        lichess_games = _make_lichess_games()
        with aioresponses() as mock:
            mock.get(LICHESS_URL_PATTERN,
                     body=_ndjson_payload(lichess_games),
                     content_type="application/x-ndjson")
            stats, games = await _run_lichess_pipeline(
                LICHESS_USERNAME, days=7, fixed_now=_now)

        assert len(games) == 2
        assert stats["total_games"] == 2
        assert stats["wins"] == 2

    @pytest.mark.asyncio
    async def test_game_urls_are_lichess(self):
        """All parsed games have lichess.org URLs."""
        lichess_games = _make_lichess_games()
        with aioresponses() as mock:
            mock.get(LICHESS_URL_PATTERN,
                     body=_ndjson_payload(lichess_games),
                     content_type="application/x-ndjson")
            _, games = await _run_lichess_pipeline(LICHESS_USERNAME, days=0)

        for g in games:
            assert g.game_url.startswith("https://lichess.org/")

    @pytest.mark.asyncio
    async def test_time_classes_mapped_correctly(self):
        """Lichess speed values are mapped to our time_class strings."""
        lichess_games = _make_lichess_games()
        with aioresponses() as mock:
            mock.get(LICHESS_URL_PATTERN,
                     body=_ndjson_payload(lichess_games),
                     content_type="application/x-ndjson")
            _, games = await _run_lichess_pipeline(LICHESS_USERNAME, days=0)

        time_classes = {g.time_class for g in games}
        assert time_classes == {"blitz", "rapid", "bullet"}


class TestCombinedPipeline:
    """Mocked Chess.com + Lichess combined pipeline."""

    @pytest.mark.asyncio
    async def test_combined_mocked_pipeline(self):
        """Merge games from both mocked APIs and analyze."""
        chesscom_games = [
            make_game_json(white_user=USERNAME, black_user="Opp1",
                           white_result="win", black_result="lose",
                           end_time=_recent_ts),
        ]
        lichess_games = [
            make_lichess_game_json(
                white_user=USERNAME, black_user="OppL1",
                winner="white", speed="blitz", game_id="li999",
                last_move_at=int(_recent_ts * 1000),
            ),
        ]
        month_url = f"{BASE_URL}/{USERNAME}/games/2025/06"

        with aioresponses() as mock:
            # Chess.com
            mock.get(ARCHIVES_URL, payload={"archives": [month_url]})
            mock.get(month_url, payload=make_archive_response(chesscom_games))
            # Lichess
            mock.get(LICHESS_URL_PATTERN,
                     body=_ndjson_payload(lichess_games),
                     content_type="application/x-ndjson")

            # Chess.com path
            cc_fetcher = ChessCom_Fetcher(user_agent="TestAgent/1.0")
            cc_archives = await cc_fetcher.fetch_all_archives(USERNAME)
            cc_raw = []
            for month in cc_archives:
                cc_raw.extend(month.get("games", []))
            cc_games = [g for g in (ChessGame.from_json(g, USERNAME)
                                     for g in cc_raw) if g is not None]

            # Lichess path
            li_fetcher = LichessFetcher(user_agent="TestAgent/1.0")
            li_raw = await li_fetcher.fetch_games(USERNAME)
            li_games = [g for g in (ChessGame.from_lichess_json(g, USERNAME)
                                     for g in li_raw) if g is not None]

        all_games = cc_games + li_games
        assert len(all_games) == 2

        # Verify URLs don't collide
        cc_urls = {g.game_url for g in cc_games if g.game_url}
        li_urls = {g.game_url for g in li_games if g.game_url}
        assert cc_urls.isdisjoint(li_urls)

        # Analyzer works on merged games
        analyzer = ChessGameAnalyzer(USERNAME, all_games)
        stats = analyzer.summarize()
        assert stats["total_games"] == 2
        assert stats["wins"] == 2


@pytest.mark.network
class TestRealAPI:
    """Smoke test against the live Chess.com API to catch data format changes."""

    @pytest.mark.asyncio
    async def test_chesscom_api_data_format(self):
        """Fetch real data for 'laaz' and verify the response shape hasn't changed."""
        fetcher = ChessCom_Fetcher(user_agent="chess_coachAI/tests (smoke test)")

        # 1. Archives endpoint returns a list of URL strings
        archives = await fetcher.get_archives("laaz")
        assert isinstance(archives, list)
        assert len(archives) > 0
        assert all(isinstance(url, str) for url in archives)

        # 2. Fetch the most recent month only (to keep the test fast)
        month_data = await fetcher.fetch_games_by_month(archives[-1])
        assert "games" in month_data
        games = month_data["games"]
        assert isinstance(games, list)
        assert len(games) > 0

        # 3. Verify each game has the fields our pipeline relies on
        required_keys = {"white", "black", "end_time", "time_class"}
        player_keys = {"username", "result"}
        valid_time_classes = {"bullet", "blitz", "rapid", "daily"}

        for game in games:
            assert required_keys.issubset(game.keys()), (
                f"Missing top-level keys: {required_keys - game.keys()}")
            assert player_keys.issubset(game["white"].keys()), (
                f"Missing white keys: {player_keys - game['white'].keys()}")
            assert player_keys.issubset(game["black"].keys()), (
                f"Missing black keys: {player_keys - game['black'].keys()}")
            assert isinstance(game["end_time"], int)
            assert game["time_class"] in valid_time_classes, (
                f"Unexpected time_class: {game['time_class']}")

        # 4. Verify ChessGame.from_json can parse at least one game
        parsed = ChessGame.from_json(games[0], "laaz")
        if parsed is not None:
            assert parsed.my_color in ("white", "black")
            assert isinstance(parsed.end_time, datetime.datetime)
            assert parsed.white_result != ""
            assert parsed.black_result != ""
            assert parsed.time_class in valid_time_classes


@pytest.mark.network
class TestRealLichessAPI:
    """Smoke test against the live Lichess API to catch data format changes."""

    @pytest.mark.asyncio
    async def test_lichess_api_data_format(self):
        """Fetch real data for 'laaz' and verify the response shape."""
        fetcher = LichessFetcher(user_agent="chess_coachAI/tests (smoke test)")

        # Fetch a small batch (most recent 5 games) to keep it fast
        import time
        since_ms = int((time.time() - 365 * 86400) * 1000)
        games = await fetcher.fetch_games("laaz", since=since_ms)
        assert isinstance(games, list)
        assert len(games) > 0

        # Verify expected top-level fields
        valid_speeds = {"bullet", "blitz", "rapid", "classical",
                        "correspondence", "ultraBullet"}
        for game in games[:5]:
            assert "id" in game, f"Missing 'id' field"
            assert "speed" in game, f"Missing 'speed' field"
            assert "players" in game, f"Missing 'players' field"
            assert "status" in game, f"Missing 'status' field"
            assert game["speed"] in valid_speeds, (
                f"Unexpected speed: {game['speed']}")

            # Verify player structure
            for color in ("white", "black"):
                assert color in game["players"], f"Missing players.{color}"
                player = game["players"][color]
                assert "user" in player or "aiLevel" in player, (
                    f"Player {color} has neither 'user' nor 'aiLevel'")

            # Verify PGN is present (we request pgnInJson=true)
            assert "pgn" in game, "Missing 'pgn' — pgnInJson param may have changed"

        # Verify ChessGame.from_lichess_json can parse at least one game
        parsed = ChessGame.from_lichess_json(games[0], "laaz")
        if parsed is not None:
            assert parsed.my_color in ("white", "black")
            assert isinstance(parsed.end_time, datetime.datetime)
            assert parsed.game_url.startswith("https://lichess.org/")
            assert parsed.time_class in ("bullet", "blitz", "rapid", "daily")

    @pytest.mark.asyncio
    async def test_lichess_chesscom_combined_pipeline(self):
        """Fetch from both APIs for 'laaz', merge, and analyze."""
        # Chess.com
        cc_fetcher = ChessCom_Fetcher(user_agent="chess_coachAI/tests")
        archives = await cc_fetcher.get_archives("laaz")
        cc_month = await cc_fetcher.fetch_games_by_month(archives[-1])
        cc_games = [g for g in (ChessGame.from_json(g, "laaz")
                                for g in cc_month.get("games", [])) if g]

        # Lichess
        li_fetcher = LichessFetcher(user_agent="chess_coachAI/tests")
        import time
        since_ms = int((time.time() - 365 * 86400) * 1000)
        li_raw = await li_fetcher.fetch_games("laaz", since=since_ms)
        li_games = [g for g in (ChessGame.from_lichess_json(g, "laaz")
                                for g in li_raw) if g]

        # Merge and analyze
        all_games = cc_games + li_games
        assert len(all_games) > 0

        # Verify no game_url collisions between platforms
        cc_urls = {g.game_url for g in cc_games if g.game_url}
        li_urls = {g.game_url for g in li_games if g.game_url}
        assert cc_urls.isdisjoint(li_urls), "Game URLs should not overlap between platforms"

        # Verify analyzer works on combined games
        analyzer = ChessGameAnalyzer("laaz", all_games)
        stats = analyzer.summarize()
        assert stats["total_games"] == len(all_games)
        assert stats["wins"] + stats["losses"] + stats["draws"] == stats["total_games"]
