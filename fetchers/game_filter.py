# fetchers/game_filter.py
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set
from chessgame import ChessGame

def filter_games_by_days(games: List[ChessGame], days: int) -> List[ChessGame]:
    """Filter games to include only those in the last `days` days."""
    if days <= 0:
        return games  # 0 or negative = all games

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    return [g for g in games if g.end_time >= cutoff]


def filter_games_by_time_class(
    games: List[ChessGame],
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
) -> List[ChessGame]:
    """Filter games by time class (bullet, blitz, rapid, daily).

    Args:
        games: List of ChessGame objects.
        include: If set, only keep games whose time_class is in this set.
        exclude: If set, remove games whose time_class is in this set.
        If both are None, returns all games. include takes priority over exclude.
    """
    if include is not None:
        return [g for g in games if g.time_class in include]
    if exclude is not None:
        return [g for g in games if g.time_class not in exclude]
    return games
