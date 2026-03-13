# Chess CoachAI

> Find your opening weaknesses. Fix your endgame habits.

Chess CoachAI analyzes your Chess.com and Lichess games using Stockfish to find where you deviate from opening theory and how you perform in endgames.

## Features

- Deep Stockfish analysis of opening deviations from book theory
- Endgame classification and win rate tracking
- Interactive web report with filters (time control, color, date, platform)
- SVG chessboard visualization with best/played move arrows
- Supports both Chess.com and Lichess accounts
- Incremental analysis — only new games are processed on sync

## Quick Start (Docker)

1. Clone the repo and copy the env file:
   ```bash
   git clone <repo-url>
   cd chess_coachAI
   cp .env.example .env
   # Edit .env to set your SECRET_KEY
   ```

2. Add the opening book:
   ```bash
   mkdir -p data
   # Place gm2001.bin in data/ (Polyglot format)
   ```

3. Start all services:
   ```bash
   docker-compose up -d
   ```

4. Visit http://localhost:8000

## CLI Usage (Local Development)

The original CLI still works for local analysis:

```bash
pip install -r requirements.txt
python analyze.py --chesscom Hikaru --lichess DrNykterstein --days 30 --depth 14 --report
```

## Architecture

```
Browser → nginx → Flask (gunicorn) → PostgreSQL
                       ↓
                  Celery Worker → Stockfish
                       ↑
                     Redis ← Flower (monitoring)
```

- **Flask** serves the landing page, reports, and admin dashboard (`/admin/jobs`)
- **Celery** runs CPU-heavy Stockfish analysis in the background
- **PostgreSQL** stores game data, evaluations, and job status
- **Redis** is the Celery message broker
- **Flower** monitors Celery workers and tasks (port 5555)

## Project Structure

```
web/        Flask routes, templates, reports
worker/     Celery tasks (analysis pipeline)
fetchers/   Game fetching, PGN parsing, Stockfish eval, opening/endgame detection
db/         PostgreSQL connection pooling, queries, migrations
data/       Polyglot opening book (gm2001.bin)
tests/      Test suite (mirrors source structure)
deploy/     Deployment scripts/configs
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://localhost/chesscoach` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `STOCKFISH_PATH` | `engines/stockfish-...exe` | Path to Stockfish binary |
| `BOOK_PATH` | `data/gm2001.bin` | Path to Polyglot opening book |
| `ANALYSIS_DEPTH` | `14` | Stockfish search depth (1-30) |
| `STOCKFISH_WORKERS` | `1` | Parallel Stockfish instances |
| `SECRET_KEY` | `dev-secret-key` | Flask secret key |

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run PostgreSQL and Redis locally (or via Docker)
docker-compose up -d postgres redis

# Run the web app
flask --app app run --port 5050 --debug

# Run the Celery worker
celery -A worker.celery_app worker --loglevel=info

# Run tests
pytest
pytest -m "not network"  # skip live API tests
```

## License

[Add your license]
