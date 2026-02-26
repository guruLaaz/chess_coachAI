import pytest
from aioresponses import aioresponses
from chesscom_fetcher import ChessCom_Fetcher, BASE_URL


@pytest.fixture
def fetcher():
    return ChessCom_Fetcher(user_agent="TestAgent/1.0")


@pytest.fixture
def mock_aiohttp():
    with aioresponses() as m:
        yield m


class TestGetArchives:
    @pytest.mark.asyncio
    async def test_returns_archive_urls(self, fetcher, mock_aiohttp):
        url = f"{BASE_URL}/testuser/games/archives"
        archive_urls = [
            f"{BASE_URL}/testuser/games/2025/01",
            f"{BASE_URL}/testuser/games/2025/02",
        ]
        mock_aiohttp.get(url, payload={"archives": archive_urls})

        result = await fetcher.get_archives("testuser")
        assert result == archive_urls

    @pytest.mark.asyncio
    async def test_empty_archives(self, fetcher, mock_aiohttp):
        url = f"{BASE_URL}/testuser/games/archives"
        mock_aiohttp.get(url, payload={"archives": []})

        result = await fetcher.get_archives("testuser")
        assert result == []

    @pytest.mark.asyncio
    async def test_http_error_raises(self, fetcher, mock_aiohttp):
        url = f"{BASE_URL}/baduser/games/archives"
        mock_aiohttp.get(url, status=404)

        with pytest.raises(Exception):
            await fetcher.get_archives("baduser")


class TestFetchGamesByMonth:
    @pytest.mark.asyncio
    async def test_returns_game_data(self, fetcher, mock_aiohttp):
        archive_url = f"{BASE_URL}/testuser/games/2025/01"
        payload = {"games": [{"white": {}, "black": {}}]}
        mock_aiohttp.get(archive_url, payload=payload)

        result = await fetcher.fetch_games_by_month(archive_url)
        assert result == payload


class TestFetchAllArchives:
    @pytest.mark.asyncio
    async def test_fetches_all_months(self, fetcher, mock_aiohttp):
        archives_url = f"{BASE_URL}/testuser/games/archives"
        month_urls = [
            f"{BASE_URL}/testuser/games/2025/01",
            f"{BASE_URL}/testuser/games/2025/02",
        ]
        mock_aiohttp.get(archives_url, payload={"archives": month_urls})

        month1 = {"games": [{"id": 1}]}
        month2 = {"games": [{"id": 2}]}
        mock_aiohttp.get(month_urls[0], payload=month1)
        mock_aiohttp.get(month_urls[1], payload=month2)

        result = await fetcher.fetch_all_archives("testuser")
        assert len(result) == 2
        assert result[0] == month1
        assert result[1] == month2
