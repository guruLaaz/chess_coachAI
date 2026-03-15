Read [README.md](README.md) for project overview, architecture, setup, and environment variables.

## Rules
- Always ask for clarification when requirements or intent are unclear — don't assume.
- Always add or update tests when changing code.
- When fixing broken tests, verify the test's scenario is still valid before changing assertions. If unclear whether the test or the code is wrong, ask the user.
- Never commit or push without explicit user approval.
- Never redeploy or change the database without explicit and specific user instruction.

## Code Patterns
- Raw SQL via psycopg2 (no ORM) — queries live in `db/queries.py`
- Async game fetchers use aiohttp (`fetchers/chesscom_fetcher.py`, `fetchers/lichess_fetcher.py`)
- PostgreSQL connection pooling via `ThreadedConnectionPool` in `db/connection.py`
- Opening theory uses Polyglot book (`data/gm2001.bin`) via python-chess
- Celery tasks in `worker/tasks.py`, app config in `worker/celery_app.py`
- Templates are Jinja2 in `web/templates/`

## Internationalization (i18n)
- The app supports English and French via a client-side translation system in `web/templates/partials/controls.html`
- All user-visible text in templates MUST use `data-i18n="key_name"` attributes with English as the default text content
- Translation strings are defined in the `translations` JS object inside `controls.html` — add both `en` and `fr` entries for every new key
- For parameterized strings (e.g., containing a username), use `{placeholder}` in translation values and pass data via `data-i18n-placeholder` attributes on the element
- Server-side error messages in `web/routes.py` should pass structured `error_keys` (list of `{key, ...params}` dicts) to templates instead of pre-formatted English strings
- The `applyLang()` function in `controls.html` handles substitution of `data-i18n-*` attributes into `{placeholder}` patterns

## Testing
- pytest with pytest-asyncio (asyncio_mode = auto)
- `pytest -m "not network"` to skip live Chess.com/Lichess API tests
- Use aioresponses for mocking async HTTP calls
- Test files in `tests/` mirror source structure

## Common Commands
- `docker-compose up -d` — run all services
- `pytest` — run tests
- Local dev: `flask --app app run --port 5050 --debug` + `celery -A worker.celery_app worker --loglevel=info`

## Frontend Development
- `cd frontend && npm run dev` — Vue dev server with hot reload (port 5173, proxies API to Flask)
- `cd frontend && npm run build` — Build Vue SPA to static/dist/
- `cd frontend && npm run test` — Run frontend unit tests (Vitest)
- Production: Flask serves the built SPA from static/dist/
