import sys
import os
from unittest.mock import MagicMock

_tests_dir = os.path.dirname(__file__)

# Add fetchers/ to the import path so tests can import modules directly
sys.path.insert(0, os.path.join(_tests_dir, '..', 'fetchers'))
# Add tests/ itself so helpers.py can be imported
sys.path.insert(0, _tests_dir)

# Keys that test files mock in sys.modules to avoid loading psycopg2.
_DB_MODULE_KEYS = ('db', 'db.queries', 'db.connection', 'db.models')


def mock_db_modules():
    """Replace db modules in sys.modules with mocks, return (mock, cleanup).

    Saves any previously-loaded real modules and restores them on cleanup,
    preventing one test file's mocks from poisoning another's real imports.
    """
    saved = {k: sys.modules.pop(k, None) for k in _DB_MODULE_KEYS}
    mock_db = MagicMock()
    sys.modules['db'] = mock_db
    sys.modules['db.queries'] = mock_db.queries
    sys.modules['db.connection'] = mock_db.connection
    sys.modules['db.models'] = mock_db.models

    def cleanup():
        for k in _DB_MODULE_KEYS:
            sys.modules.pop(k, None)
        for k, orig in saved.items():
            if orig is not None:
                sys.modules[k] = orig

    return mock_db, cleanup
