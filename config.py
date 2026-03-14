"""Shared configuration for Chess CoachAI, read from environment variables."""

import collections
import logging
import os
import sys
import threading
import time

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


class MemoryLogHandler(logging.Handler):
    """Ring-buffer handler that keeps the most recent log records in memory."""

    def __init__(self, capacity=500):
        super().__init__()
        self._buffer = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record):
        entry = {
            "timestamp": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
        }
        with self._lock:
            self._buffer.append(entry)

    def get_logs(self, level=None, limit=200):
        """Return recent logs, optionally filtered by minimum level."""
        min_level = getattr(logging, level, 0) if level else 0
        with self._lock:
            logs = list(self._buffer)
        if min_level:
            logs = [l for l in logs if getattr(logging, l["level"], 0) >= min_level]
        return logs[-limit:]


# Singleton — importable from anywhere to read buffered logs
memory_log_handler = MemoryLogHandler(capacity=500)


def setup_logging():
    """Configure logging for the entire application.

    Call once at startup (Flask app factory or Celery worker).
    """
    root = logging.getLogger()

    # Always attach the memory handler (idempotent check)
    if memory_log_handler not in root.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        memory_log_handler.setFormatter(fmt)
        root.addHandler(memory_log_handler)

    # Only add stderr handler once
    has_stream = any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, MemoryLogHandler)
        for h in root.handlers
    )
    if not has_stream:
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
