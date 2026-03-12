"""Async fetcher for the Lichess API."""

import aiohttp
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

LICHESS_API_BASE = "https://lichess.org/api"


class LichessFetcher:
    """Fetches game data from the Lichess API (NDJSON streaming)."""

    def __init__(self, user_agent: str = "chess_coachAI/1.0"):
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/x-ndjson",
        }

    async def fetch_games(
        self,
        username: str,
        since: Optional[int] = None,
    ) -> List[dict]:
        """Fetch all games for a Lichess user as a list of JSON dicts.

        Args:
            username: Lichess username (case-insensitive).
            since: Optional Unix timestamp in milliseconds (earliest game).

        Returns:
            List of Lichess game JSON objects.
        """
        url = f"{LICHESS_API_BASE}/games/user/{username}"
        params = {
            "pgnInJson": "true",
            "opening": "true",
        }
        if since is not None:
            params["since"] = str(since)

        logger.info("Fetching Lichess games for '%s'", username)
        games = []
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                async for line in resp.content:
                    line = line.strip()
                    if line:
                        games.append(json.loads(line))
        logger.info("Fetched %d Lichess games for '%s'", len(games), username)
        return games
