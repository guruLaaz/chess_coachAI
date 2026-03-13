"""Database query functions for Chess CoachAI.

Mirrors the GameCache method signatures but uses PostgreSQL via psycopg2.
"""

import json
import logging
from datetime import datetime, timezone

from psycopg2.extras import RealDictCursor

from db.connection import get_connection
from fetchers.repertoire_analyzer import OpeningEvaluation
from fetchers.endgame_detector import EndgameInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_evaluation(row):
    """Convert a database row (dict) to an OpeningEvaluation."""
    book_moves_raw = row["book_moves_uci"] or ""
    game_moves_raw = row["game_moves_uci"] or ""
    return OpeningEvaluation(
        eco_code=row["eco_code"],
        eco_name=row["eco_name"],
        my_color=row["my_color"],
        deviation_ply=row["deviation_ply"],
        deviating_side=row["deviating_side"],
        eval_cp=row["eval_cp"],
        is_fully_booked=bool(row["is_fully_booked"]),
        fen_at_deviation=row["fen_at_deviation"] or "",
        best_move_uci=row["best_move_uci"],
        played_move_uci=row["played_move_uci"],
        book_moves_uci=book_moves_raw.split(",") if book_moves_raw else [],
        eval_loss_cp=row["eval_loss_cp"] if row["eval_loss_cp"] is not None else 0,
        game_moves_uci=game_moves_raw.split(",") if game_moves_raw else [],
        game_url=row.get("game_url", ""),
        my_result=row.get("my_result", ""),
        time_class=row.get("time_class", ""),
        opponent_name=row.get("opponent_name", ""),
        end_time=row.get("end_time"),
    )


def _row_to_endgame(row):
    """Convert a database row (dict) to an EndgameInfo or None."""
    if row["endgame_type"] is None:
        return None
    return EndgameInfo(
        endgame_type=row["endgame_type"],
        endgame_ply=row["endgame_ply"],
        material_balance=row["material_balance"],
        my_result=row["my_result"],
        fen_at_endgame=row["fen_at_endgame"] or "",
        game_url=row["game_url_link"] or "",
        material_diff=row["material_diff"] or 0,
        my_clock=row["my_clock"],
        opp_clock=row["opp_clock"],
    )


def _chunked_query(cur, sql_template, keys, extra_params=()):
    """Execute a query in 500-key batches. Use {placeholders} in template."""
    rows = []
    for i in range(0, len(keys), 500):
        chunk = keys[i:i + 500]
        placeholders = ",".join(["%s"] * len(chunk))
        cur.execute(
            sql_template.format(placeholders=placeholders),
            (*chunk, *extra_params),
        )
        rows.extend(cur.fetchall())
    return rows


# ---------------------------------------------------------------------------
# Archive caching
# ---------------------------------------------------------------------------

def get_archive(archive_url):
    """Return cached JSON dict for an archive month, or None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT raw_json FROM archive_months WHERE archive_url = %s",
                (archive_url,),
            )
            row = cur.fetchone()
            if row:
                raw = row["raw_json"]
                logger.debug("Archive cache hit: %s", archive_url)
                return raw if isinstance(raw, dict) else json.loads(raw)
            logger.debug("Archive cache miss: %s", archive_url)
            return None


def save_archive(archive_url, username, data):
    """Cache an archive month's JSON (upsert)."""
    game_count = len(data.get("games", []))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO archive_months (archive_url, username, raw_json, fetched_at)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (archive_url) DO UPDATE
                   SET username = EXCLUDED.username,
                       raw_json = EXCLUDED.raw_json,
                       fetched_at = EXCLUDED.fetched_at""",
                (archive_url, username.lower(), json.dumps(data),
                 datetime.now(timezone.utc)),
            )
        conn.commit()
    logger.debug("Saved archive %s for %s (%d games)", archive_url, username, game_count)


# ---------------------------------------------------------------------------
# Evaluation caching
# ---------------------------------------------------------------------------

_EVAL_COLUMNS = """game_url, eco_code, eco_name, my_color, deviation_ply,
    deviating_side, eval_cp, is_fully_booked,
    fen_at_deviation, best_move_uci, played_move_uci,
    book_moves_uci, eval_loss_cp, game_moves_uci,
    my_result, time_class, opponent_name, end_time"""


def get_cached_evaluations(game_urls, depth):
    """Batch lookup: return dict of game_url -> OpeningEvaluation for all hits."""
    if not game_urls:
        return {}

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            rows = _chunked_query(
                cur,
                f"""SELECT {_EVAL_COLUMNS}
                    FROM opening_evaluations
                    WHERE game_url IN ({{placeholders}}) AND depth = %s""",
                game_urls,
                extra_params=(depth,),
            )

    results = {}
    for row in rows:
        results[row["game_url"]] = _row_to_evaluation(row)
    logger.info("Evaluation cache: %d/%d hits (depth=%d)", len(results), len(game_urls), depth)
    return results


def _eval_insert_params(game_url, username, depth, ev):
    """Build parameter tuple for evaluation upsert."""
    return (
        game_url, username.lower(), depth,
        ev.eco_code, ev.eco_name, ev.my_color,
        ev.deviation_ply, ev.deviating_side,
        ev.eval_cp, ev.is_fully_booked,
        ev.fen_at_deviation,
        ev.best_move_uci,
        ev.played_move_uci,
        ",".join(ev.book_moves_uci) if ev.book_moves_uci else "",
        ev.eval_loss_cp,
        ",".join(ev.game_moves_uci) if ev.game_moves_uci else "",
        ev.my_result or "",
        ev.time_class or "",
        getattr(ev, "opponent_name", "") or "",
        getattr(ev, "end_time", None),
    )


_INSERT_EVAL_SQL = """INSERT INTO opening_evaluations
    (game_url, username, depth, eco_code, eco_name, my_color,
     deviation_ply, deviating_side, eval_cp, is_fully_booked,
     fen_at_deviation, best_move_uci, played_move_uci, book_moves_uci,
     eval_loss_cp, game_moves_uci, my_result, time_class,
     opponent_name, end_time)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (game_url, depth) DO UPDATE SET
        username = EXCLUDED.username,
        eco_code = EXCLUDED.eco_code,
        eco_name = EXCLUDED.eco_name,
        my_color = EXCLUDED.my_color,
        deviation_ply = EXCLUDED.deviation_ply,
        deviating_side = EXCLUDED.deviating_side,
        eval_cp = EXCLUDED.eval_cp,
        is_fully_booked = EXCLUDED.is_fully_booked,
        fen_at_deviation = EXCLUDED.fen_at_deviation,
        best_move_uci = EXCLUDED.best_move_uci,
        played_move_uci = EXCLUDED.played_move_uci,
        book_moves_uci = EXCLUDED.book_moves_uci,
        eval_loss_cp = EXCLUDED.eval_loss_cp,
        game_moves_uci = EXCLUDED.game_moves_uci,
        my_result = EXCLUDED.my_result,
        time_class = EXCLUDED.time_class,
        opponent_name = EXCLUDED.opponent_name,
        end_time = EXCLUDED.end_time"""


def save_evaluations_batch(username, depth, evals):
    """Batch insert evaluations. evals is list of (game_url, OpeningEvaluation)."""
    if not evals:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            for game_url, ev in evals:
                cur.execute(
                    _INSERT_EVAL_SQL,
                    _eval_insert_params(game_url, username, depth, ev),
                )
        conn.commit()
    logger.info("Saved %d evaluations for %s (depth=%d)", len(evals), username, depth)


def get_all_evaluations_for_user(username, depth):
    """Load ALL evaluations for a user at a given depth."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""SELECT {_EVAL_COLUMNS}
                    FROM opening_evaluations
                    WHERE username = %s AND depth = %s""",
                (username.lower(), depth),
            )
            rows = cur.fetchall()

    return [_row_to_evaluation(row) for row in rows]


# ---------------------------------------------------------------------------
# Endgame caching
# ---------------------------------------------------------------------------

_ENDGAME_COLUMNS = """game_url, definition, endgame_type, endgame_ply,
    material_balance, my_result, fen_at_endgame,
    material_diff, game_url_link, my_clock, opp_clock"""


def _endgame_insert_params(game_url, definition, info):
    """Build parameter tuple for endgame upsert."""
    if info is None:
        return (game_url, definition,
                None, None, None, None, None, None, "",
                None, None)
    return (game_url, definition,
            info.endgame_type, info.endgame_ply,
            info.material_balance, info.my_result,
            info.fen_at_endgame, info.material_diff,
            info.game_url,
            info.my_clock, info.opp_clock)


_INSERT_ENDGAME_SQL = """INSERT INTO endgame_analyses
    (game_url, definition, endgame_type, endgame_ply,
     material_balance, my_result, fen_at_endgame, material_diff,
     game_url_link, my_clock, opp_clock)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (game_url, definition) DO UPDATE SET
        endgame_type = EXCLUDED.endgame_type,
        endgame_ply = EXCLUDED.endgame_ply,
        material_balance = EXCLUDED.material_balance,
        my_result = EXCLUDED.my_result,
        fen_at_endgame = EXCLUDED.fen_at_endgame,
        material_diff = EXCLUDED.material_diff,
        game_url_link = EXCLUDED.game_url_link,
        my_clock = EXCLUDED.my_clock,
        opp_clock = EXCLUDED.opp_clock"""


def save_endgames_batch(rows):
    """Batch insert endgame results.

    rows: list of (game_url, definition, EndgameInfo_or_None).
    """
    if not rows:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            for game_url, definition, info in rows:
                cur.execute(
                    _INSERT_ENDGAME_SQL,
                    _endgame_insert_params(game_url, definition, info),
                )
        conn.commit()
    logger.info("Saved %d endgame rows", len(rows))


def get_endgames(game_urls):
    """Batch lookup endgame results.

    Returns dict of game_url -> dict of definition -> EndgameInfo or None.
    """
    if not game_urls:
        return {}

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            rows = _chunked_query(
                cur,
                f"""SELECT {_ENDGAME_COLUMNS}
                    FROM endgame_analyses
                    WHERE game_url IN ({{placeholders}})""",
                game_urls,
            )

    results = {}
    for row in rows:
        url = row["game_url"]
        defn = row["definition"]
        if url not in results:
            results[url] = {}
        results[url][defn] = _row_to_endgame(row)

    return results


def get_all_endgames_for_user(game_urls):
    """Load endgames for a list of game URLs (same format as get_endgames)."""
    return get_endgames(game_urls)


# ---------------------------------------------------------------------------
# Job tracking
# ---------------------------------------------------------------------------

def create_job(chesscom_user=None, lichess_user=None):
    """Create a new analysis job and return its id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO analysis_jobs (chesscom_user, lichess_user)
                   VALUES (%s, %s) RETURNING id""",
                (chesscom_user, lichess_user),
            )
            job_id = cur.fetchone()[0]
        conn.commit()
    logger.info("Created job %s (chesscom=%s, lichess=%s)", job_id, chesscom_user, lichess_user)
    return job_id


def update_job(job_id, status=None, progress_pct=None, total_games=None,
               message=None, error_message=None):
    """Update fields on an analysis job."""
    if status:
        logger.debug("Job %s -> status=%s pct=%s msg=%s", job_id, status, progress_pct, message)
    sets = []
    params = []
    if status is not None:
        sets.append("status = %s")
        params.append(status)
        if status == "complete":
            sets.append("completed_at = NOW()")
            if error_message is None:
                sets.append("error_message = NULL")
        elif status == "failed":
            sets.append("completed_at = NOW()")
    if progress_pct is not None:
        sets.append("progress_pct = %s")
        params.append(progress_pct)
    if total_games is not None:
        sets.append("total_games = %s")
        params.append(total_games)
    if message is not None:
        sets.append("message = %s")
        params.append(message)
    if error_message is not None:
        sets.append("error_message = %s")
        params.append(error_message)
    if not sets:
        return

    params.append(job_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE analysis_jobs SET {', '.join(sets)} WHERE id = %s",
                params,
            )
        conn.commit()


def get_job(job_id):
    """Return a job as a dict, or None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM analysis_jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_latest_job(chesscom_user=None, lichess_user=None):
    """Find the most recent job for these usernames."""
    conditions = []
    params = []
    if chesscom_user:
        conditions.append("chesscom_user = %s")
        params.append(chesscom_user)
    if lichess_user:
        conditions.append("lichess_user = %s")
        params.append(lichess_user)
    if not conditions:
        return None

    where = " AND ".join(conditions)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM analysis_jobs WHERE {where} ORDER BY created_at DESC LIMIT 1",
                params,
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_queue_position(job_id):
    """Return (position, total) for a pending job in the queue.

    position is 1-based (1 = next up). Returns (0, 0) if not pending.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM analysis_jobs
                   WHERE status = 'pending'
                     AND created_at <= (SELECT created_at FROM analysis_jobs WHERE id = %s)""",
                (job_id,),
            )
            position = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'pending'",
            )
            total = cur.fetchone()[0]
    if position == 0:
        return (0, 0)
    return (position, total)


def cancel_job(job_id):
    """Cancel a pending job. Marks as failed instead of deleting so the
    Celery task (if any) can detect it and stop early."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE analysis_jobs
                   SET status = 'failed',
                       error_message = 'Cancelled by user',
                       completed_at = NOW()
                   WHERE id = %s AND status = 'pending'""",
                (job_id,),
            )
            updated = cur.rowcount
        conn.commit()
    if updated:
        logger.info("Cancelled pending job %s", job_id)
    return updated > 0


def append_job_log(job_id, level, message):
    """Append a log line for a job."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO job_logs (job_id, level, message) VALUES (%s, %s, %s)",
                (job_id, level, message[:2000]),
            )
        conn.commit()


def get_job_logs(job_id):
    """Return all log lines for a job, oldest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT logged_at, level, message
                   FROM job_logs
                   WHERE job_id = %s
                   ORDER BY logged_at ASC, id ASC""",
                (job_id,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_all_jobs(limit=100):
    """Return recent jobs ordered by created_at desc, with computed duration."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT *,
                          EXTRACT(EPOCH FROM
                              COALESCE(completed_at, NOW()) - created_at
                          )::int AS duration_seconds
                   FROM analysis_jobs
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]
