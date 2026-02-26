# fetchers/chesscom.py

import aiohttp
from typing import List

BASE_URL = "https://api.chess.com/pub/player"

class ChessCom_Fetcher:
    """
    Fetches game data from the Chess.com public API.
    """

    def __init__(self, user_agent: str = "MyApp/1.0 (contact: your@email.com)"):
        self.headers = {"User-Agent": user_agent}

    async def get_archives(self, username: str) -> List[str]:
        """
        Return a list of monthly archive URLs for the username.
        """
        url = f"{BASE_URL}/{username}/games/archives"
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("archives", [])

    async def fetch_games_by_month(self, archive_url: str) -> dict:
        """
        Fetch the games JSON for a single monthly archive URL.
        """
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(archive_url) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def fetch_all_archives(self, username: str) -> List[dict]:
        """
        Fetch all monthly archive JSONs for the user.
        (Just returns raw JSON for now)
        """
        archives = await self.get_archives(username)
        results = []
        for url in archives:
            month_data = await self.fetch_games_by_month(url)
            results.append(month_data)
        return results
