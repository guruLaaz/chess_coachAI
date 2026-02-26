<!-- .github/copilot-instructions.md -->
# Copilot / AI-Agent Instructions for this repository

Purpose: give an AI coding agent immediate, actionable context so it can be productive.

**Big picture**
- This repo currently contains a small `fetchers` package whose primary role is to fetch game data from the Chess.com public API. The single implementation is `fetchers/chesscom_fetcher.py` which exposes `ChessComFetcher` (async APIs).
- Tests / examples live in `fetchers/chesscom_fetcher_test.py` — they are simple runner scripts that call the async methods directly.

**Key files**
- `fetchers/chesscom_fetcher.py`: main implementation. Uses `aiohttp` and async/await. Creates `ClientSession` for each request and returns raw JSON.
- `fetchers/chesscom_fetcher_test.py`: example runner. Shows usage pattern: instantiate `ChessComFetcher()`, call `get_archives()` and `fetch_games_by_month()`.

**Developer workflows (how to run & test locally)**
- Install runtime dependency: `pip install aiohttp` (there is no requirements.txt).
- Run the example/test script from the repository root:

```powershell
python fetchers/chesscom_fetcher_test.py
```

Notes: the tests are not pytest-based; they are small asyncio scripts that call `asyncio.run(main())`.

**Repository-specific patterns and gotchas**
- Async-first: network functions are `async def` and must be awaited. Use `asyncio` or an async test harness when adding new examples.
- Header and User-Agent: the fetcher sets a `User-Agent` header in `__init__`. Preserve or update this header when making requests to avoid being blocked.
- Per-call sessions: the current implementation creates an `aiohttp.ClientSession` in each method call. If you need high-performance loads or many requests, prefer reusing a session — but only change this if you update all call-sites accordingly.

**Concrete, discoverable issues to check before editing**
- The repository appears to have a mismatch between the module filename and the import used in the test: the test imports `fetchers.chesscom` while the file is named `fetchers/chesscom_fetcher.py`. Confirm and either:
  - rename the module to `chesscom.py`, or
  - update the test to import `from fetchers.chesscom_fetcher import ChessComFetcher`.
- Some source files may contain Markdown code fences (```python) at the top/bottom — remove those so files are valid Python.

**Integration points & external assumptions**
- External API: https://api.chess.com/pub/player (rate limits and network availability matter). Unit tests that hit the network are integration-style and require network access.
- Dependency: `aiohttp` is required at runtime.

**How to propose a change**
- If you modify HTTP behavior (headers, session reuse, error handling), add or update a small example script under `fetchers/` that demonstrates the new behavior.
- Keep changes minimal and locally scoped; this repo is small and changes should be surgical.

If anything here is unclear or you want the instructions to include additional conventions (branching, commit message format, CI steps, or a requirements file), tell me which area to expand and I'll update this file.
