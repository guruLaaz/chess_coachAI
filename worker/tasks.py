"""Celery task that runs the chess analysis pipeline in the background."""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone

# Add fetchers/ to import path (matching analyze.py's approach)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fetchers"))

from worker.celery_app import app
from config import STOCKFISH_PATH, BOOK_PATH, ANALYSIS_DEPTH, STOCKFISH_WORKERS, setup_logging
import db.queries as dbq

setup_logging()

from chesscom_fetcher import ChessCom_Fetcher
from lichess_fetcher import LichessFetcher
from chessgame import ChessGame
from opening_detector import OpeningDetector
from stockfish_evaluator import StockfishEvaluator
from repertoire_analyzer import RepertoireAnalyzer
from endgame_detector import EndgameClassifier, ENDGAME_DEFINITIONS

logger = logging.getLogger(__name__)


def _is_current_month(archive_url):
    """Check if an archive URL is for the current year/month."""
    match = re.search(r"/(\d{4})/(\d{2})$", archive_url)
    if not match:
        return True
    year, month = int(match.group(1)), int(match.group(2))
    now = datetime.now(timezone.utc)
    return year == now.year and month == now.month


async def _fetch_chesscom_games(username, job_id=None):
    """Fetch Chess.com games, using DB archive cache for completed months."""
    fetcher = ChessCom_Fetcher(user_agent="chess_coachAI/1.0")
    archive_urls = await fetcher.get_archives(username)
    total_archives = len(archive_urls)
    logger.info("Chess.com: %d archives to process for '%s'", total_archives, username)

    raw_games = []
    for i, url in enumerate(archive_urls, 1):
        try:
            cached_data = dbq.get_archive(url)
            if cached_data and not _is_current_month(url):
                raw_games.extend(cached_data.get("games", []))
            else:
                month_data = await fetcher.fetch_games_by_month(url)
                raw_games.extend(month_data.get("games", []))
                dbq.save_archive(url, username, month_data)
        except Exception:
            logger.error("Failed to fetch/cache Chess.com archive %s", url, exc_info=True)
        try:
            if job_id and (i % 3 == 0 or i == total_archives):
                pct = 5 + int(20 * i / total_archives)
                dbq.update_job(job_id, progress_pct=pct,
                               message=f"Fetching Chess.com archive {i}/{total_archives} ({len(raw_games)} games)")
        except Exception:
            logger.warning("Failed to update job progress for archive %d", i)

    games = []
    for g in raw_games:
        try:
            game = ChessGame.from_json(g, username)
            if game is not None:
                games.append(game)
        except Exception:
            logger.warning("Failed to parse Chess.com game JSON", exc_info=True)
    logger.info("Chess.com: fetched %d raw, %d valid games for '%s'",
                len(raw_games), len(games), username)
    return games


async def _get_lichess_game_count(username):
    """Get total game count from Lichess user profile."""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://lichess.org/api/user/{username}",
                headers={"Accept": "application/json"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    count = data.get("count", {}).get("all", 0)
                    logger.debug("Lichess game count for '%s': %d", username, count)
                    return count
    except Exception:
        logger.warning("Failed to get Lichess game count for '%s'", username, exc_info=True)
    return 0


async def _fetch_lichess_games(username, job_id=None):
    """Fetch Lichess games with progress reporting."""
    total_estimate = 0
    if job_id:
        total_estimate = await _get_lichess_game_count(username)
        dbq.update_job(job_id, message=f"Fetching Lichess games... (0/{total_estimate})" if total_estimate else "Fetching Lichess games...")

    import aiohttp, json as _json
    url = f"https://lichess.org/api/games/user/{username}"
    params = {"pgnInJson": "true", "opening": "true"}
    raw_games = []
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "chess_coachAI/1.0", "Accept": "application/x-ndjson"}) as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                async for line in resp.content:
                    line = line.strip()
                    if line:
                        try:
                            raw_games.append(_json.loads(line))
                        except (ValueError, _json.JSONDecodeError):
                            logger.warning("Bad NDJSON line from Lichess for '%s', skipping", username)
                        if job_id and len(raw_games) % 50 == 0:
                            try:
                                msg = f"Fetching Lichess games... ({len(raw_games)}/{total_estimate})" if total_estimate else f"Fetching Lichess games... ({len(raw_games)} so far)"
                                dbq.update_job(job_id, message=msg)
                            except Exception:
                                pass
    except Exception:
        logger.error("Failed to fetch Lichess games for '%s'", username, exc_info=True)

    try:
        if job_id:
            dbq.update_job(job_id, message=f"Fetched {len(raw_games)} Lichess games")
    except Exception:
        pass

    games = []
    for g in raw_games:
        try:
            game = ChessGame.from_lichess_json(g, username)
            if game is not None:
                games.append(game)
        except Exception:
            logger.warning("Failed to parse Lichess game JSON", exc_info=True)
    return games


async def _fetch_all(chesscom_user, lichess_user, job_id=None):
    """Fetch games from both platforms."""
    all_games = []
    # Fetch sequentially so progress messages don't interleave
    if chesscom_user:
        try:
            games = await _fetch_chesscom_games(chesscom_user, job_id)
            all_games.extend(games)
        except Exception:
            logger.error("Chess.com fetch failed for '%s'", chesscom_user, exc_info=True)
    if lichess_user:
        try:
            games = await _fetch_lichess_games(lichess_user, job_id)
            all_games.extend(games)
        except Exception:
            logger.error("Lichess fetch failed for '%s'", lichess_user, exc_info=True)
    return all_games


@app.task(name="worker.analyze_user", bind=True)
def analyze_user(self, job_id, chesscom_user=None, lichess_user=None):
    """Run full analysis pipeline as a background Celery task.

    Steps: fetch games -> endgame analysis -> opening analysis (Stockfish).
    Updates job progress in the database throughout.
    """
    try:
        import time as _time
        job_start = _time.monotonic()

        # ------------------------------------------------------------------
        # Phase 1: Fetch games
        # ------------------------------------------------------------------
        dbq.update_job(job_id, status="fetching", progress_pct=5)
        logger.info("Job %s: fetching games (chesscom=%s, lichess=%s)",
                     job_id, chesscom_user, lichess_user)

        fetch_start = _time.monotonic()
        games = asyncio.run(_fetch_all(chesscom_user, lichess_user, job_id))
        logger.info("Job %s: fetch phase took %.1fs", job_id, _time.monotonic() - fetch_start)

        if not games:
            logger.warning("Job %s: no games found for chesscom=%s, lichess=%s",
                           job_id, chesscom_user, lichess_user)
            dbq.update_job(job_id, status="complete", progress_pct=100,
                           total_games=0, message="No games found.")
            return {"job_id": job_id, "total_games": 0}

        total = len(games)
        logger.info("Job %s: fetched %d total games, starting analysis", job_id, total)
        dbq.update_job(job_id, status="analyzing", total_games=total,
                       progress_pct=30,
                       message=f"Fetched {total} games, starting analysis")

        # ------------------------------------------------------------------
        # Phase 2: Endgame analysis (fast, no Stockfish)
        # ------------------------------------------------------------------
        game_urls = [g.game_url for g in games if g.game_url]
        cached_endgames = dbq.get_endgames(game_urls)

        uncached_endgame_games = [
            g for g in games
            if g.game_url not in cached_endgames
            or len(cached_endgames[g.game_url]) < len(ENDGAME_DEFINITIONS)
        ]
        logger.info("Job %s: endgame analysis — %d cached, %d to analyze",
                     job_id, len(cached_endgames), len(uncached_endgame_games))

        new_rows = []
        for game in uncached_endgame_games:
            try:
                all_results = EndgameClassifier.analyze_game_all(game)
                for defn, info in all_results.items():
                    new_rows.append((game.game_url, defn, info))
            except Exception:
                logger.error("Endgame analysis failed for game %s",
                             getattr(game, 'game_url', 'unknown'), exc_info=True)

        if new_rows:
            dbq.save_endgames_batch(new_rows)
            logger.info("Job %s: saved %d endgame rows", job_id, len(new_rows))

        logger.info("Job %s: endgame phase took %.1fs", job_id, _time.monotonic() - fetch_start)

        try:
            dbq.update_job(job_id, progress_pct=40,
                           message=f"Endgame analysis complete, starting openings")
        except Exception:
            logger.warning("Failed to update job progress after endgame phase")

        # ------------------------------------------------------------------
        # Phase 3: Opening analysis (Stockfish, slow)
        # ------------------------------------------------------------------
        opening_start = _time.monotonic()
        depth = ANALYSIS_DEPTH
        workers = STOCKFISH_WORKERS

        cached_map = dbq.get_cached_evaluations(game_urls, depth)
        cached_evals = list(cached_map.values()) if cached_map else []
        cached_urls = set(cached_map.keys()) if cached_map else set()
        uncached_games = [g for g in games if g.game_url not in cached_urls]

        username = chesscom_user or lichess_user
        logger.info("Job %s: opening analysis — %d cached, %d to analyze (depth=%d, workers=%d)",
                     job_id, len(cached_evals), len(uncached_games), depth, workers)

        if not uncached_games and cached_evals:
            # Everything cached — no engine work needed
            logger.info("Job %s: all evaluations cached, skipping engine", job_id)
            dbq.update_job(job_id, progress_pct=95,
                           message="All games cached, skipping engine analysis")
            new_evals = []
        else:
            detector = OpeningDetector(BOOK_PATH)

            def progress_callback(current, batch_total):
                # Map engine progress from 40% to 95%
                pct = 40 + int(55 * current / max(batch_total, 1))
                pct = min(pct, 95)
                if current % 5 == 0 or current == batch_total:
                    try:
                        dbq.update_job(
                            job_id, progress_pct=pct,
                            message=f"Analyzing game {current}/{batch_total}")
                    except Exception:
                        pass

            with StockfishEvaluator(STOCKFISH_PATH, depth=depth) as evaluator:
                rep_analyzer = RepertoireAnalyzer(username, detector, evaluator)
                _opening_stats, new_evals = rep_analyzer.analyze_repertoire(
                    uncached_games,
                    progress_callback=progress_callback,
                    workers=workers,
                    cached_evaluations=cached_evals,
                )

            # Save newly computed evaluations
            if new_evals:
                batch = [(game.game_url, ev)
                         for game, ev in new_evals if game.game_url]
                if batch:
                    dbq.save_evaluations_batch(username, depth, batch)

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        logger.info("Job %s: opening phase took %.1fs", job_id, _time.monotonic() - opening_start)
        total_elapsed = _time.monotonic() - job_start
        dbq.update_job(job_id, status="complete", progress_pct=100,
                       message=f"Analysis complete: {total} games in {total_elapsed:.0f}s")
        logger.info("Job %s: complete (%d games, %.1fs total)", job_id, total, total_elapsed)
        return {"job_id": job_id, "total_games": total}

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        dbq.update_job(job_id, status="failed",
                       error_message=str(exc)[:500])
        raise
