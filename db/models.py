"""Re-export the dataclasses used by the DB layer.

These are the canonical definitions from the fetchers package.
"""

from fetchers.repertoire_analyzer import OpeningEvaluation
from fetchers.endgame_detector import EndgameInfo

__all__ = ["OpeningEvaluation", "EndgameInfo"]
