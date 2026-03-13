Read [README.md](README.md) for project overview, architecture, setup, and environment variables.

## Rules
- Always ask for clarification when requirements or intent are unclear — don't assume.
- Always add or update tests when changing code.
- When fixing broken tests, verify the test's scenario is still valid before changing assertions. If unclear whether the test or the code is wrong, ask the user.
- Never commit or push without explicit user approval.

## Code Patterns
- Raw SQL via psycopg2 (no ORM) — queries live in `db/queries.py`
- Async game fetchers use aiohttp (`fetchers/chesscom_fetcher.py`, `fetchers/lichess_fetcher.py`)
- PostgreSQL connection pooling via `ThreadedConnectionPool` in `db/connection.py`
- Opening theory uses Polyglot book (`data/gm2001.bin`) via python-chess
- Celery tasks in `worker/tasks.py`, app config in `worker/celery_app.py`
- Templates are Jinja2 in `web/templates/`

## Testing
- pytest with pytest-asyncio (asyncio_mode = auto)
- `pytest -m "not network"` to skip live Chess.com/Lichess API tests
- Use aioresponses for mocking async HTTP calls
- Test files in `tests/` mirror source structure

## Common Commands
- `docker-compose up -d` — run all services
- `pytest` — run tests
- Local dev: `flask --app app run --port 5050 --debug` + `celery -A worker.celery_app worker --loglevel=info`
