# Chess CoachAI

A CLI tool that analyzes your Chess.com opening repertoire using Stockfish, identifies where you deviate from book theory, and generates an interactive coaching report showing your biggest mistakes with move-by-move recommendations.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)

## What It Does

1. **Fetches** all your games from the Chess.com API (with intelligent caching)
2. **Detects** where each game deviates from opening book theory
3. **Evaluates** deviation positions with Stockfish to measure the cost of your moves
4. **Groups** repeated mistakes so you see patterns, not noise
5. **Generates** a web-based coaching report sorted by biggest blunders first

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Analyze last 30 days of blitz games and open the coaching report
python analyze.py YOUR_USERNAME 30 --include blitz --report

# Full analysis with 4 Stockfish workers at depth 20
python analyze.py YOUR_USERNAME --depth 20 --workers 4 --report

# Only show mistakes you've made 3+ times
python analyze.py YOUR_USERNAME 60 --report --min-times 3
```

## Prerequisites

### Stockfish Engine

Download Stockfish from [stockfishchess.org](https://stockfishchess.org/download/) and place the binary at:

```
engines/stockfish-windows-x86-64-avx2.exe
```

Or specify a custom path with `--stockfish /path/to/stockfish`.

### Opening Book

Place a Polyglot opening book (`.bin` format) at:

```
data/gm2001.bin
```

Or specify a custom path with `--book /path/to/book.bin`. Polyglot books can be generated from PGN databases using tools like `pgn-extract` or downloaded from various chess resources.

## CLI Reference

```
python analyze.py USERNAME [DAYS] [OPTIONS]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `USERNAME` | *required* | Chess.com username |
| `DAYS` | `0` (all) | Only analyze games from the last N days |
| `--depth` | `18` | Stockfish analysis depth (higher = slower but more accurate) |
| `--workers` | `1` | Parallel Stockfish instances (use CPU core count) |
| `--report` | off | Launch the coaching report web app |
| `--min-times` | `1` | Only show deviations that occurred N+ times |
| `--include` | all | Only include specific time controls: `bullet blitz rapid daily` |
| `--exclude` | none | Exclude specific time controls: `bullet blitz rapid daily` |
| `--no-cache` | off | Force re-fetch and re-analysis (still saves new results to cache) |
| `--stockfish` | `engines/stockfish-...` | Path to Stockfish binary |
| `--book` | `data/gm2001.bin` | Path to Polyglot opening book |

`--include` and `--exclude` are mutually exclusive.

## Coaching Report

The `--report` flag launches a Flask web app at `http://127.0.0.1:5050` with:

- **Deviation cards** sorted by eval loss (biggest mistakes first)
- **SVG board diagrams** showing the best move (green arrow) vs your move (red arrow)
- **Sidebar navigation** to filter by opening (ECO code) and color
- **Occurrence badges** showing how many times you made each mistake
- **Game links** to view the original game on Chess.com
- **Min-times filter** subtitle when active

## How It Works

```
Chess.com API ─→ Parse PGN ─→ Detect Book Deviation ─→ Stockfish Eval ─→ Report
                     │                                        │
                     └──── SQLite Cache (archives) ───────────┘
                                                   (evaluations)
```

**Opening detection**: Each game's moves are compared against a Polyglot opening book move-by-move. The first non-book move is the "deviation point."

**Eval loss**: At the deviation point, Stockfish evaluates both the position before and after the played move. The difference is the eval loss — how many centipawns your move cost compared to the book/engine recommendation.

**Grouping**: Identical mistakes (same position + same played move across multiple games) are collapsed into a single entry with an occurrence count. The `--min-times` flag filters out one-off deviations to focus on habitual mistakes.

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
│   ├── chessgame.py            # Game data model
│   ├── chessgameanalyzer.py    # Win/loss/draw statistics
│   ├── game_filter.py          # Filter by days and time control
│   ├── pgn_parser.py           # PGN → move list parser
│   ├── opening_detector.py     # Polyglot book deviation detection
│   ├── stockfish_evaluator.py  # Stockfish engine wrapper
│   ├── repertoire_analyzer.py  # Core analysis pipeline (sequential + parallel)
│   ├── game_cache.py           # SQLite caching layer
│   └── report_generator.py     # Flask coaching report web app
│
├── engines/                    # Stockfish binary (gitignored)
├── data/                       # Opening book + cache DB (gitignored)
│
└── tests/                      # 234 tests, 98% coverage
    ├── helpers.py              # Test data factories
    ├── test_analyze.py
    ├── test_chesscom_fetcher.py
    ├── test_chessgame.py
    ├── test_chessgameanalyzer.py
    ├── test_game_filter.py
    ├── test_game_cache.py
    ├── test_opening_detector.py
    ├── test_pgn_parser.py
    ├── test_repertoire_analyzer.py
    ├── test_stockfish_evaluator.py
    ├── test_report_generator.py
    └── test_integration.py
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=fetchers --cov=analyze --cov-report=term-missing
```

**234 tests** across 13 test files with **98% overall coverage**. All `fetchers/` modules are at 100%.

## Dependencies

| Package | Purpose |
|---------|---------|
| `aiohttp` | Async HTTP client for Chess.com API |
| `python-chess` | PGN parsing, board representation, Stockfish UCI integration |
| `flask` | Coaching report web server |
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `pytest-cov` | Coverage reporting |
| `aioresponses` | Mock HTTP responses in tests |
