# fetchers/chesscom.py

import logging
import aiohttp
from typing import List

logger = logging.getLogger(__name__)

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
        Returns empty list if the user is not found (404) or on any error.
        """
        url = f"{BASE_URL}/{username}/games/archives"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url) as resp:
                    if resp.status == 404:
                        logger.warning("Chess.com user '%s' not found (404)", username)
                        return []
                    resp.raise_for_status()
                    data = await resp.json()
                    archives = data.get("archives", [])
                    logger.info("Chess.com user '%s': %d monthly archives found", username, len(archives))
                    return archives
        except Exception:
            logger.error("Failed to fetch Chess.com archives for '%s'", username, exc_info=True)
            return []

    async def fetch_games_by_month(self, archive_url: str) -> dict:
        """
        Fetch the games JSON for a single monthly archive URL.
        Returns empty games list on 404 or any error.
        """
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(archive_url) as resp:
                    if resp.status == 404:
                        logger.warning("Chess.com archive 404, skipping: %s", archive_url)
                        return {"games": []}
                    resp.raise_for_status()
                    return await resp.json()
        except Exception:
            logger.error("Failed to fetch Chess.com archive %s", archive_url, exc_info=True)
            return {"games": []}
