# Chess CoachAI

A CLI tool that analyzes your Chess.com and Lichess opening repertoire using Stockfish, identifies where you deviate from book theory, and generates an interactive coaching report showing your biggest mistakes with move-by-move recommendations.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)

## What It Does

1. **Fetches** all your games from Chess.com and/or Lichess (concurrently, with intelligent caching)
2. **Detects** where each game deviates from opening book theory
3. **Evaluates** deviation positions with Stockfish to measure the cost of your moves
4. **Classifies** endgames by piece type and material balance, with win/loss/draw stats
5. **Groups** repeated mistakes so you see patterns, not noise
6. **Generates** a web-based coaching report sorted by biggest blunders first

## Quick Start

```bash
# Set up a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Analyze Chess.com games from the last 30 days
python analyze.py YOUR_CHESSCOM_USER "" 30 --include blitz --report

# Analyze Lichess games only
python analyze.py "" YOUR_LICHESS_USER 60 --report

# Analyze both platforms at once
python analyze.py YOUR_CHESSCOM_USER YOUR_LICHESS_USER 90 --report

# Full analysis with 4 Stockfish workers at depth 20
python analyze.py YOUR_CHESSCOM_USER "" --depth 20 --workers 4 --report

```

Use `""` to skip a platform.

## Prerequisites

### Stockfish Engine

Download Stockfish from [stockfishchess.org](https://stockfishchess.org/download/) and place the binary at:

```
engines/stockfish-windows-x86-64-sse41-popcnt.exe
```

Or specify a custom path with `--stockfish /path/to/stockfish`.

### Opening Book

Place a Polyglot opening book (`.bin` format) at:

```
data/gm2001.bin
```

Or specify a custom path with `--book /path/to/book.bin`. Polyglot books can be generated from PGN databases using tools like `pgn-extract` or downloaded from various chess resources.

## Setup

```bash
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

## CLI Reference

```
python analyze.py [CHESSCOM_USER] [LICHESS_USER] [DAYS] [OPTIONS]
```

At least one username is required. Use `""` to skip a platform.

| Argument | Default | Description |
|----------|---------|-------------|
| `CHESSCOM_USER` | `""` (skip) | Chess.com username |
| `LICHESS_USER` | `""` (skip) | Lichess username |
| `DAYS` | `0` (all) | Only analyze games from the last N days |
| `--depth` | `18` | Stockfish analysis depth (higher = slower but more accurate) |
| `--workers` | `1` | Parallel Stockfish instances (use CPU core count) |
| `--report` | off | Launch the coaching report web app |
| `--include` | all | Only include specific time controls: `bullet blitz rapid daily` |
| `--exclude` | none | Exclude specific time controls: `bullet blitz rapid daily` |
| `--no-cache` | off | Force re-fetch and re-analysis (still saves new results to cache) |
| `--stockfish` | `engines/stockfish-...` | Path to Stockfish binary |
| `--book` | `data/gm2001.bin` | Path to Polyglot opening book |

`--include` and `--exclude` are mutually exclusive.

## Coaching Report

The `--report` flag launches a Flask web app at `http://127.0.0.1:5050` with two pages:

### Openings

- **Deviation cards** sorted by eval loss (biggest mistakes first)
- **SVG board diagrams** showing the best move (green arrow) vs your move (red arrow)
- **Sidebar navigation** to filter by opening (ECO code) and color
- **Occurrence badges** showing how many times you made each mistake
- **Game links** to view the original game on Chess.com or Lichess
- **Interactive filters**: sort by eval loss or loss%, filter by time control, platform, and min games

### Endgames

- **Three endgame definitions** (all computed and cached; filter in the report):
  - **Queens off** — no queens remain on the board
  - **Minor or queen** (default) — no queens, or each queen has at most 1 minor and 0 rooks
  - **Material** — each side's non-pawn piece material &le; 9 points (Q=9, R=5, B=3, N=3)
- **Endgame cards** grouped by piece type (e.g. R vs R, Q vs -, RB vs R) and material balance (up / equal / down)
- **Win/loss/draw percentages** per endgame type
- **Average clock time** remaining (you vs opponent) when entering the endgame
- **Example board positions** with deep-links that open the game at the endgame move
- **Filters**: definition selector, sort by games/win%/loss%/draw%, filter by material balance and min games

## How It Works

```
Chess.com API ─┐
               ├─→ Parse PGN ─→ Detect Book Deviation ─→ Stockfish Eval ─→ Report
Lichess API ───┘       │              │                         │
                       │              └── Endgame Detection ────┘
                       └──── SQLite Cache (archives) ───────────┘
                                                     (evaluations)
```

**Opening detection**: Each game's moves are compared against a Polyglot opening book move-by-move. The first non-book move is the "deviation point."

**Eval loss**: At the deviation point, Stockfish evaluates both the position before and after the played move. The difference is the eval loss — how many centipawns your move cost compared to the book/engine recommendation.

**Endgame detection**: Every game is analyzed with all three endgame definitions in a single replay pass. Results are cached in SQLite and filtered by definition in the report UI. Clock annotations from PGNs are captured to show average time remaining when entering the endgame. No Stockfish needed.

**Grouping**: Identical mistakes (same position + same played move across multiple games) are collapsed into a single entry with an occurrence count. The min-games dropdown in the report (default: 3+) filters out one-off deviations to focus on habitual mistakes.

**Caching**: Archives from completed months and evaluation results are cached in SQLite (`data/cache.db`). Re-running analysis skips already-evaluated games. The current month is always re-fetched. Use `--no-cache` to force a full re-analysis.

## Project Structure

```
chess_coachAI/
├── analyze.py                  # CLI entry point
├── requirements.txt
├── pytest.ini
│
├── fetchers/
│   ├── chesscom_fetcher.py     # Async Chess.com API client
│   ├── lichess_fetcher.py      # Async Lichess API client (NDJSON streaming)
│   ├── chessgame.py            # Game data model (Chess.com + Lichess parsers)
│   ├── chessgameanalyzer.py    # Win/loss/draw statistics
│   ├── game_filter.py          # Filter by days and time control
│   ├── pgn_parser.py           # PGN → move list parser
│   ├── opening_detector.py     # Polyglot book deviation detection
│   ├── stockfish_evaluator.py  # Stockfish engine wrapper
│   ├── repertoire_analyzer.py  # Core analysis pipeline (sequential + parallel)
│   ├── endgame_detector.py     # Endgame detection & classification
│   ├── game_cache.py           # SQLite caching layer
│   └── report_generator.py     # Flask coaching report web app
│
├── engines/                    # Stockfish binary (gitignored)
├── data/                       # Opening book + cache DB (gitignored)
│
└── tests/                      # 436 tests across 14 test files
    ├── helpers.py              # Test data factories
    ├── test_analyze.py
    ├── test_chesscom_fetcher.py
    ├── test_lichess_fetcher.py
    ├── test_chessgame.py
    ├── test_chessgameanalyzer.py
    ├── test_game_filter.py
    ├── test_game_cache.py
    ├── test_opening_detector.py
    ├── test_pgn_parser.py
    ├── test_repertoire_analyzer.py
    ├── test_endgame_detector.py
    ├── test_stockfish_evaluator.py
    ├── test_report_generator.py
    └── test_integration.py
```

## Testing

```bash
# Run all tests (excluding live API calls)
pytest tests/ -v -m "not network"

# Run all tests including live API smoke tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=fetchers --cov=analyze --cov-report=term-missing
```

**436 tests** across 14 test files. Tests marked with `@pytest.mark.network` hit live APIs and can be skipped with `-m "not network"`.

## Dependencies

| Package | Purpose |
|---------|---------|
| `aiohttp` | Async HTTP client for Chess.com and Lichess APIs |
| `chess` | PGN parsing, board representation, Stockfish UCI integration |
| `flask` | Coaching report web server |
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `pytest-cov` | Coverage reporting |
| `aioresponses` | Mock HTTP responses in tests |
