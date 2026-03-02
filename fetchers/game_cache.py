# game_cache.py

import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from repertoire_analyzer import OpeningEvaluation
from endgame_detector import EndgameInfo


class GameCache:
    """SQLite cache for Chess.com archive data and opening evaluations."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS archive_months (
                archive_url TEXT PRIMARY KEY,
                username    TEXT NOT NULL,
                raw_json    TEXT NOT NULL,
                fetched_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS opening_evaluations (
                game_url       TEXT NOT NULL,
                username       TEXT NOT NULL,
                depth          INTEGER NOT NULL,
                eco_code       TEXT,
                eco_name       TEXT NOT NULL,
                my_color       TEXT NOT NULL,
                deviation_ply  INTEGER NOT NULL,
                deviating_side TEXT NOT NULL,
                eval_cp        INTEGER NOT NULL,
                is_fully_booked INTEGER NOT NULL,
                PRIMARY KEY (game_url, depth)
            );

            CREATE TABLE IF NOT EXISTS endgame_analyses (
                game_url          TEXT NOT NULL,
                definition        TEXT NOT NULL,
                endgame_type      TEXT,
                endgame_ply       INTEGER,
                material_balance  TEXT,
                my_result         TEXT,
                fen_at_endgame    TEXT,
                material_diff     INTEGER,
                game_url_link     TEXT DEFAULT '',
                my_clock          REAL,
                opp_clock         REAL,
                PRIMARY KEY (game_url, definition)
            );
        """)
        self._conn.commit()
        self._migrate_endgame_columns()
        self._migrate_coaching_columns()

    def _migrate_endgame_columns(self):
        """Add clock columns to endgame_analyses if they don't exist."""
        for col_name, col_type in [("my_clock", "REAL"), ("opp_clock", "REAL")]:
            try:
                self._conn.execute(
                    f"ALTER TABLE endgame_analyses ADD COLUMN {col_name} {col_type}"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
        self._conn.commit()

    def _migrate_coaching_columns(self):
        """Add coaching columns if they don't exist (schema v2)."""
        new_columns = [
            ("fen_at_deviation", "TEXT DEFAULT ''"),
            ("best_move_uci", "TEXT"),
            ("played_move_uci", "TEXT"),
            ("book_moves_uci", "TEXT DEFAULT ''"),
            ("eval_loss_cp", "INTEGER DEFAULT 0"),
            ("game_moves_uci", "TEXT DEFAULT ''"),
            ("my_result", "TEXT DEFAULT ''"),
            ("time_class", "TEXT DEFAULT ''"),
        ]
        for col_name, col_type in new_columns:
            try:
                self._conn.execute(
                    f"ALTER TABLE opening_evaluations ADD COLUMN {col_name} {col_type}"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
        self._conn.commit()

    # --- Archive caching ---

    def get_archive(self, archive_url):
        """Return cached JSON dict for an archive month, or None."""
        row = self._conn.execute(
            "SELECT raw_json FROM archive_months WHERE archive_url = ?",
            (archive_url,)
        ).fetchone()
        if row:
            return json.loads(row["raw_json"])
        return None

    def save_archive(self, archive_url, username, data):
        """Cache an archive month's JSON (upsert)."""
        self._conn.execute(
            """INSERT OR REPLACE INTO archive_months
               (archive_url, username, raw_json, fetched_at)
               VALUES (?, ?, ?, ?)""",
            (archive_url, username.lower(), json.dumps(data),
             datetime.now(timezone.utc).isoformat())
        )
        self._conn.commit()

    # --- Evaluation caching ---

    @staticmethod
    def _row_to_evaluation(row):
        """Convert a database row to an OpeningEvaluation."""
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
            game_url=row["game_url"] if "game_url" in row.keys() else "",
            my_result=row["my_result"] if "my_result" in row.keys() else "",
            time_class=row["time_class"] if "time_class" in row.keys() else "",
        )

    def get_evaluation(self, game_url, depth):
        """Return a cached OpeningEvaluation, or None."""
        row = self._conn.execute(
            """SELECT game_url, eco_code, eco_name, my_color, deviation_ply,
                      deviating_side, eval_cp, is_fully_booked,
                      fen_at_deviation, best_move_uci, played_move_uci,
                      book_moves_uci, eval_loss_cp, game_moves_uci,
                      my_result, time_class
               FROM opening_evaluations
               WHERE game_url = ? AND depth = ?""",
            (game_url, depth)
        ).fetchone()
        if row:
            return self._row_to_evaluation(row)
        return None

    def get_cached_evaluations(self, game_urls, depth):
        """Batch lookup: return dict of game_url -> OpeningEvaluation for all hits."""
        if not game_urls:
            return {}

        results = {}
        # SQLite has a variable limit; process in chunks of 500
        for i in range(0, len(game_urls), 500):
            chunk = game_urls[i:i + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"""SELECT game_url, eco_code, eco_name, my_color, deviation_ply,
                           deviating_side, eval_cp, is_fully_booked,
                           fen_at_deviation, best_move_uci, played_move_uci,
                           book_moves_uci, eval_loss_cp, game_moves_uci,
                           my_result, time_class
                    FROM opening_evaluations
                    WHERE game_url IN ({placeholders}) AND depth = ?""",
                (*chunk, depth)
            ).fetchall()

            for row in rows:
                results[row["game_url"]] = self._row_to_evaluation(row)

        return results

    @staticmethod
    def _eval_to_row(game_url, username, depth, evaluation):
        """Convert an OpeningEvaluation to a tuple for SQL insert."""
        return (
            game_url, username.lower(), depth,
            evaluation.eco_code, evaluation.eco_name, evaluation.my_color,
            evaluation.deviation_ply, evaluation.deviating_side,
            evaluation.eval_cp, int(evaluation.is_fully_booked),
            evaluation.fen_at_deviation,
            evaluation.best_move_uci,
            evaluation.played_move_uci,
            ",".join(evaluation.book_moves_uci) if evaluation.book_moves_uci else "",
            evaluation.eval_loss_cp,
            ",".join(evaluation.game_moves_uci) if evaluation.game_moves_uci else "",
            evaluation.my_result or "",
            evaluation.time_class or "",
        )

    _INSERT_EVAL_SQL = """INSERT OR REPLACE INTO opening_evaluations
        (game_url, username, depth, eco_code, eco_name, my_color,
         deviation_ply, deviating_side, eval_cp, is_fully_booked,
         fen_at_deviation, best_move_uci, played_move_uci, book_moves_uci,
         eval_loss_cp, game_moves_uci, my_result, time_class)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    def save_evaluation(self, game_url, username, depth, evaluation):
        """Cache a single opening evaluation (upsert)."""
        self._conn.execute(
            self._INSERT_EVAL_SQL,
            self._eval_to_row(game_url, username, depth, evaluation)
        )
        self._conn.commit()

    def save_evaluations_batch(self, username, depth, evals):
        """Batch insert evaluations. evals is list of (game_url, OpeningEvaluation)."""
        rows = [
            self._eval_to_row(game_url, username, depth, ev)
            for game_url, ev in evals
        ]
        self._conn.executemany(self._INSERT_EVAL_SQL, rows)
        self._conn.commit()

    # --- Endgame caching ---

    _INSERT_ENDGAME_SQL = """INSERT OR REPLACE INTO endgame_analyses
        (game_url, definition, endgame_type, endgame_ply,
         material_balance, my_result, fen_at_endgame, material_diff,
         game_url_link, my_clock, opp_clock)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    def save_endgames_batch(self, rows):
        """Batch insert endgame results.

        rows: list of (game_url, definition, EndgameInfo_or_None).
        None means no endgame was reached for that definition.
        """
        sql_rows = []
        for game_url, definition, info in rows:
            if info is None:
                sql_rows.append((game_url, definition,
                                 None, None, None, None, None, None, "",
                                 None, None))
            else:
                sql_rows.append((game_url, definition,
                                 info.endgame_type, info.endgame_ply,
                                 info.material_balance, info.my_result,
                                 info.fen_at_endgame, info.material_diff,
                                 info.game_url,
                                 info.my_clock, info.opp_clock))
        self._conn.executemany(self._INSERT_ENDGAME_SQL, sql_rows)
        self._conn.commit()

    def get_endgames(self, game_urls):
        """Batch lookup endgame results.

        Returns dict of game_url -> dict of definition -> EndgameInfo or None.
        Only returns entries for game_urls that exist in the cache.
        """
        if not game_urls:
            return {}

        results = {}
        for i in range(0, len(game_urls), 500):
            chunk = game_urls[i:i + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"""SELECT game_url, definition, endgame_type, endgame_ply,
                           material_balance, my_result, fen_at_endgame,
                           material_diff, game_url_link, my_clock, opp_clock
                    FROM endgame_analyses
                    WHERE game_url IN ({placeholders})""",
                chunk
            ).fetchall()

            for row in rows:
                url = row["game_url"]
                defn = row["definition"]
                if url not in results:
                    results[url] = {}
                if row["endgame_type"] is None:
                    results[url][defn] = None
                else:
                    results[url][defn] = EndgameInfo(
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

        return results

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
