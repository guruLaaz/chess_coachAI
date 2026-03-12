"""Shared configuration for Chess CoachAI, read from environment variables."""

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/chesscoach")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
STOCKFISH_PATH = os.environ.get(
    "STOCKFISH_PATH", "engines/stockfish-windows-x86-64-avx2.exe"
)
BOOK_PATH = os.environ.get("BOOK_PATH", "data/gm2001.bin")
ANALYSIS_DEPTH = int(os.environ.get("ANALYSIS_DEPTH", "14"))
STOCKFISH_WORKERS = int(os.environ.get("STOCKFISH_WORKERS", "1"))
