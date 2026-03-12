"""Shared configuration for Chess CoachAI, read from environment variables."""

import logging
import os
import sys

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/chesscoach")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
STOCKFISH_PATH = os.environ.get(
    "STOCKFISH_PATH", "engines/stockfish-windows-x86-64-avx2.exe"
)
BOOK_PATH = os.environ.get("BOOK_PATH", "data/gm2001.bin")
ANALYSIS_DEPTH = int(os.environ.get("ANALYSIS_DEPTH", "14"))
STOCKFISH_WORKERS = int(os.environ.get("STOCKFISH_WORKERS", "1"))

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


def setup_logging():
    """Configure logging for the entire application.

    Call once at startup (Flask app factory, Celery worker, or CLI).
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Quieten noisy third-party loggers
    logging.getLogger("chess.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
