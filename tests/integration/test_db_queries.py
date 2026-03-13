"""Tests for db.queries against a real PostgreSQL database.

Uses testcontainers to spin up an ephemeral PostgreSQL container automatically.
Falls back to TEST_DATABASE_URL env var if set (e.g. for CI with a service container).
Each test runs inside a transaction that is rolled back, so the DB stays clean.
"""

import os
import sys
import pytest

# Ensure project root is on the path so `from db...` and `from fetchers...` work.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "fetchers"))

import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor

from fetchers.repertoire_analyzer import OpeningEvaluation
from fetchers.endgame_detector import EndgameInfo

# We'll monkey-patch db.connection so every query uses our rolled-back transaction.
import db.connection as _db_conn
import db.queries as queries


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "db", "migrations"
)


def _collect_migration_sql():
    """Read all migration .sql files in order."""
    sql_files = sorted(
        f for f in os.listdir(_MIGRATIONS_DIR) if f.endswith(".sql")
    )
    parts = []
    for fname in sql_files:
        with open(os.path.join(_MIGRATIONS_DIR, fname)) as f:
            parts.append(f.read())
    return "\n".join(parts)


@pytest.fixture(scope="session")
def _database_url():
    """Return a database URL, spinning up a container if needed."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        yield explicit
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip(
            "testcontainers[postgres] not installed and TEST_DATABASE_URL not set"
        )

    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url().replace("+psycopg2", "")


class _NoCommitConnection:
    """Proxy that wraps a real psycopg2 connection but suppresses commit().

    psycopg2's C-extension marks `commit` as read-only, so we can't
    monkeypatch it directly.  This proxy delegates everything except
    commit() to the underlying connection.
    """

    def __init__(self, real_conn):
        self._conn = real_conn

    def commit(self):  # no-op
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture(autouse=True)
def _transactional_db(monkeypatch, _database_url):
    """Wrap every test in a transaction that gets rolled back.

    We replace db.connection.get_connection with a context manager that
    always returns the same connection (with autocommit off), and we
    ignore commits so the rollback at the end actually undoes everything.
    """
    conn = psycopg2.connect(_database_url)
    conn.autocommit = False

    # Apply all migrations inside the transaction so tables exist.
    schema_sql = _collect_migration_sql()
    with conn.cursor() as cur:
        cur.execute(schema_sql)

    wrapper = _NoCommitConnection(conn)

    from contextlib import contextmanager

    @contextmanager
    def fake_get_connection():
        yield wrapper

    monkeypatch.setattr(_db_conn, "get_connection", fake_get_connection)
    monkeypatch.setattr(queries, "get_connection", fake_get_connection)

    yield conn

    conn.rollback()
    conn.close()


def _make_eval(**overrides):
    """Build an OpeningEvaluation with sensible defaults."""
    defaults = dict(
        eco_code="B20",
        eco_name="Sicilian Defence",
        my_color="white",
        deviation_ply=6,
        deviating_side="opponent",
        eval_cp=45,
        is_fully_booked=False,
        fen_at_deviation="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        best_move_uci="e2e4",
        played_move_uci="d2d4",
        book_moves_uci=["e2e4", "d2d4"],
        eval_loss_cp=10,
        game_moves_uci=["e2e4", "c7c5"],
        game_url="",
        my_result="win",
        time_class="rapid",
        opponent_name="opponent1",
        end_time=None,
    )
    defaults.update(overrides)
    return OpeningEvaluation(**defaults)


def _make_endgame(**overrides):
    """Build an EndgameInfo with sensible defaults."""
    defaults = dict(
        endgame_type="R vs R",
        endgame_ply=60,
        material_balance="equal",
        my_result="win",
        fen_at_endgame="8/8/8/8/8/8/8/8 w - - 0 1",
        game_url="https://chess.com/game/123",
        material_diff=0,
        my_clock=120.0,
        opp_clock=90.0,
    )
    defaults.update(overrides)
    return EndgameInfo(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestArchive:
    def test_round_trip(self):
        data = {"games": [{"url": "g1"}]}
        queries.save_archive("https://api.chess.com/pub/player/bob/games/2024/01", "Bob", data)
        result = queries.get_archive("https://api.chess.com/pub/player/bob/games/2024/01")
        assert result == data

    def test_get_missing_returns_none(self):
        assert queries.get_archive("https://no-such-url") is None

    def test_upsert_overwrites(self):
        url = "https://api.chess.com/pub/player/bob/games/2024/02"
        queries.save_archive(url, "bob", {"v": 1})
        queries.save_archive(url, "bob", {"v": 2})
        assert queries.get_archive(url) == {"v": 2}


class TestEvaluations:
    def test_round_trip(self):
        ev = _make_eval()
        game_url = "https://chess.com/game/100"
        queries.save_evaluations_batch("testuser", 20, [(game_url, ev)])
        result = queries.get_cached_evaluations([game_url], 20)
        assert game_url in result
        got = result[game_url]
        assert got.eco_code == ev.eco_code
        assert got.eco_name == ev.eco_name
        assert got.my_color == ev.my_color
        assert got.deviation_ply == ev.deviation_ply
        assert got.eval_cp == ev.eval_cp
        assert got.is_fully_booked == ev.is_fully_booked
        assert got.book_moves_uci == ev.book_moves_uci
        assert got.game_moves_uci == ev.game_moves_uci
        assert got.eval_loss_cp == ev.eval_loss_cp
        assert got.my_result == ev.my_result
        assert got.time_class == ev.time_class

    def test_empty_urls_returns_empty(self):
        assert queries.get_cached_evaluations([], 20) == {}

    def test_upsert_no_duplicate(self):
        ev = _make_eval(eval_cp=10)
        game_url = "https://chess.com/game/200"
        queries.save_evaluations_batch("user", 20, [(game_url, ev)])
        ev2 = _make_eval(eval_cp=99)
        queries.save_evaluations_batch("user", 20, [(game_url, ev2)])
        result = queries.get_cached_evaluations([game_url], 20)
        assert result[game_url].eval_cp == 99

    def test_batch_500_plus_keys(self):
        """Verify chunked queries work with >500 keys."""
        evals = []
        urls = []
        for i in range(550):
            url = f"https://chess.com/game/batch_{i}"
            urls.append(url)
            evals.append((url, _make_eval(eco_name=f"Opening {i}")))
        queries.save_evaluations_batch("chunkuser", 20, evals)
        result = queries.get_cached_evaluations(urls, 20)
        assert len(result) == 550
        assert result[urls[0]].eco_name == "Opening 0"
        assert result[urls[549]].eco_name == "Opening 549"

    def test_get_all_evaluations_for_user(self):
        for i in range(3):
            queries.save_evaluations_batch(
                "alluser", 20,
                [(f"https://chess.com/game/all_{i}", _make_eval(eco_name=f"E{i}"))],
            )
        result = queries.get_all_evaluations_for_user("alluser", 20)
        assert len(result) == 3
        names = {e.eco_name for e in result}
        assert names == {"E0", "E1", "E2"}


class TestEndgames:
    def test_round_trip(self):
        info = _make_endgame()
        game_url = "https://chess.com/game/eg1"
        queries.save_endgames_batch([(game_url, "R vs R", info)])
        result = queries.get_endgames([game_url])
        assert game_url in result
        got = result[game_url]["R vs R"]
        assert got.endgame_type == "R vs R"
        assert got.endgame_ply == 60
        assert got.material_balance == "equal"
        assert got.my_result == "win"
        assert got.my_clock == 120.0
        assert got.opp_clock == 90.0

    def test_none_endgame(self):
        game_url = "https://chess.com/game/eg_none"
        queries.save_endgames_batch([(game_url, "Q vs Q", None)])
        result = queries.get_endgames([game_url])
        assert result[game_url]["Q vs Q"] is None

    def test_upsert_no_duplicate(self):
        game_url = "https://chess.com/game/eg_dup"
        queries.save_endgames_batch([
            (game_url, "R vs R", _make_endgame(my_result="loss")),
        ])
        queries.save_endgames_batch([
            (game_url, "R vs R", _make_endgame(my_result="win")),
        ])
        result = queries.get_endgames([game_url])
        assert result[game_url]["R vs R"].my_result == "win"

    def test_get_all_endgames_for_user(self):
        urls = [f"https://chess.com/game/aeg_{i}" for i in range(3)]
        rows = [(url, "Pawn", _make_endgame()) for url in urls]
        queries.save_endgames_batch(rows)
        result = queries.get_all_endgames_for_user(urls)
        assert len(result) == 3


class TestJobs:
    def test_create_and_get(self):
        job_id = queries.create_job(chesscom_user="alice")
        job = queries.get_job(job_id)
        assert job is not None
        assert job["chesscom_user"] == "alice"
        assert job["status"] == "pending"
        assert job["progress_pct"] == 0

    def test_update_status(self):
        job_id = queries.create_job(chesscom_user="bob")
        queries.update_job(job_id, status="fetching", progress_pct=25,
                           message="Fetching archives...")
        job = queries.get_job(job_id)
        assert job["status"] == "fetching"
        assert job["progress_pct"] == 25
        assert job["message"] == "Fetching archives..."

    def test_complete_sets_completed_at(self):
        job_id = queries.create_job(chesscom_user="charlie")
        queries.update_job(job_id, status="complete", progress_pct=100)
        job = queries.get_job(job_id)
        assert job["status"] == "complete"
        assert job["completed_at"] is not None

    def test_failed_sets_completed_at(self):
        job_id = queries.create_job(chesscom_user="dave")
        queries.update_job(job_id, status="failed", error_message="timeout")
        job = queries.get_job(job_id)
        assert job["status"] == "failed"
        assert job["completed_at"] is not None
        assert job["error_message"] == "timeout"

    def test_get_missing_job(self):
        assert queries.get_job(999999) is None

    def test_state_transitions(self):
        job_id = queries.create_job(chesscom_user="eve", lichess_user="eve_li")
        for status, pct in [("fetching", 10), ("analyzing", 50), ("complete", 100)]:
            queries.update_job(job_id, status=status, progress_pct=pct)
        job = queries.get_job(job_id)
        assert job["status"] == "complete"
        assert job["progress_pct"] == 100

    def test_get_latest_job(self):
        queries.create_job(chesscom_user="frank")
        j2 = queries.create_job(chesscom_user="frank")
        latest = queries.get_latest_job(chesscom_user="frank")
        assert latest is not None
        assert latest["id"] == j2

    def test_get_latest_job_no_match(self):
        assert queries.get_latest_job(chesscom_user="nobody") is None

    def test_cancel_job_marks_failed(self):
        """cancel_job should mark job as failed, not delete it."""
        job_id = queries.create_job(chesscom_user="canceller")
        result = queries.cancel_job(job_id)
        assert result is True
        job = queries.get_job(job_id)
        assert job is not None  # Row still exists
        assert job["status"] == "failed"
        assert job["error_message"] == "Cancelled by user"
        assert job["completed_at"] is not None

    def test_cancel_job_only_pending(self):
        """cancel_job should only affect pending jobs."""
        job_id = queries.create_job(chesscom_user="running")
        queries.update_job(job_id, status="analyzing", progress_pct=50)
        result = queries.cancel_job(job_id)
        assert result is False
        job = queries.get_job(job_id)
        assert job["status"] == "analyzing"

    def test_complete_clears_error_message(self):
        """Setting status=complete should clear any stale error_message."""
        job_id = queries.create_job(chesscom_user="stale")
        queries.update_job(job_id, status="failed",
                           error_message="Worker restarted")
        job = queries.get_job(job_id)
        assert job["error_message"] == "Worker restarted"

        queries.update_job(job_id, status="complete", progress_pct=100)
        job = queries.get_job(job_id)
        assert job["status"] == "complete"
        assert job["error_message"] is None

    def test_complete_with_explicit_error_keeps_it(self):
        """If error_message is explicitly passed with complete, keep it."""
        job_id = queries.create_job(chesscom_user="explicit")
        queries.update_job(job_id, status="complete", progress_pct=100,
                           error_message="Partial failure")
        job = queries.get_job(job_id)
        assert job["error_message"] == "Partial failure"


class TestJobLogs:
    def test_append_and_get_logs(self):
        job_id = queries.create_job(chesscom_user="logger")
        queries.append_job_log(job_id, "INFO", "Starting analysis")
        queries.append_job_log(job_id, "ERROR", "Something went wrong")
        logs = queries.get_job_logs(job_id)
        assert len(logs) == 2
        assert logs[0]["level"] == "INFO"
        assert logs[0]["message"] == "Starting analysis"
        assert logs[1]["level"] == "ERROR"
        assert logs[1]["message"] == "Something went wrong"

    def test_get_logs_empty(self):
        job_id = queries.create_job(chesscom_user="silent")
        logs = queries.get_job_logs(job_id)
        assert logs == []

    def test_message_truncation(self):
        job_id = queries.create_job(chesscom_user="verbose")
        long_msg = "x" * 3000
        queries.append_job_log(job_id, "INFO", long_msg)
        logs = queries.get_job_logs(job_id)
        assert len(logs[0]["message"]) == 2000


class TestConnectionPool:
    """Exercise the real connection pool in db.connection.

    These tests use the pool directly, so we override the autouse
    _transactional_db fixture to be a no-op for this class.
    """

    @pytest.fixture(autouse=True)
    def _transactional_db(self, _database_url):
        """Override the module-level autouse fixture — no-op here."""
        self.db_url = _database_url
        _db_conn.close_pool()
        yield
        _db_conn.close_pool()

    def test_init_get_close_lifecycle(self):
        """init_pool → get_connection → close_pool full lifecycle."""
        _db_conn.init_pool(self.db_url)
        with _db_conn.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ping")
                assert cur.fetchone()[0] == 1

    def test_get_connection_returns_to_pool(self):
        """Connection is returned to pool after context manager exits."""
        _db_conn.init_pool(self.db_url)

        # Get and release a connection twice — should reuse pooled conn
        for _ in range(2):
            with _db_conn.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")

    def test_get_connection_rolls_back_on_error(self):
        """On exception, the connection is rolled back and returned."""
        _db_conn.init_pool(self.db_url)

        with pytest.raises(psycopg2.ProgrammingError):
            with _db_conn.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM nonexistent_table_xyz")

        # Pool should still be usable — rollback cleared the failed txn
        with _db_conn.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1

    def test_close_pool_idempotent(self):
        """Calling close_pool when no pool exists should not raise."""
        _db_conn.close_pool()
        _db_conn.close_pool()  # second call should be a no-op

    def test_init_pool_replaces_existing(self):
        """Calling init_pool again closes old pool and creates new one."""
        _db_conn.init_pool(self.db_url)
        _db_conn.init_pool(self.db_url)  # should close old, create new

        with _db_conn.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
