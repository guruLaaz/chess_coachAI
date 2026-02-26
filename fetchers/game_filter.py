# fetchers/game_filter.py
from datetime import datetime, timedelta, timezone
from typing import List
from chessgame import ChessGame

def filter_games_by_days(games: List[ChessGame], days: int) -> List[ChessGame]:
    """Filter games to include only those in the last `days` days."""
    if days <= 0:
        return games  # 0 or negative = all games

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    return [g for g in games if g.end_time >= cutoff]
