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
   After code changes, rebuild before restarting:
   ```bash
   docker-compose up -d --build
   ```

4. Visit http://localhost:8000

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

## Internationalization (i18n)

The app supports English and French via a client-side translation system.

**How it works:**
- All translatable text lives in a `translations` JS object in `web/templates/partials/controls.html`
- HTML elements use `data-i18n="key_name"` attributes; the `applyLang()` function swaps text when the user toggles language
- The EN/FR toggle is in the site controls bar (top-right)

**Adding a new translatable string:**

1. Add the translation key to the `translations` object in `controls.html`:
   ```js
   'my_new_key': { en: 'Hello, {name}!', fr: 'Bonjour, {name}\u00a0!' },
   ```
2. Use `data-i18n` in your template, with English as the default content:
   ```html
   <span data-i18n="my_new_key" data-i18n-name="Alice">Hello, Alice!</span>
   ```
3. For parameterized strings, use `{placeholder}` in translation values and pass data via `data-i18n-placeholder` HTML attributes.

**Server-side errors:** Instead of returning pre-formatted English strings, pass structured `error_keys` to templates (list of `{key, ...params}` dicts) so the template can render them with `data-i18n` attributes.

## License

[Add your license]
