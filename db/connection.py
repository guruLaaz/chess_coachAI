import os
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    """Lazily initialize the connection pool on first use."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                database_url = os.environ.get(
                    "DATABASE_URL",
                    "postgresql://localhost/chesscoach",
                )
                _pool = ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    dsn=database_url,
                )
    return _pool


def init_pool(database_url=None):
    """Explicitly initialize the pool (useful for tests or custom URLs)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
        dsn = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql://localhost/chesscoach",
        )
        _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=dsn)


def close_pool():
    """Shut down all connections in the pool."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


@contextmanager
def get_connection():
    """Get a connection from the pool; returns it when done."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
