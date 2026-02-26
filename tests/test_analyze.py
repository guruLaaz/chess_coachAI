"""Tests for analyze.py utility functions."""
import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyze import _is_current_month, fetch_games


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
