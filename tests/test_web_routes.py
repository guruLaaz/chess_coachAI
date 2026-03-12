"""Tests for the Flask web app: URL parser, routes, and validation."""

import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from web.utils import parse_user_path, build_user_path

# Mock the db module before importing web.routes / web.app so psycopg2 is
# never loaded.  We create a mock 'queries' sub-object that individual tests
# can configure via patch('web.routes.queries').
_mock_db = MagicMock()
sys.modules.setdefault('db', _mock_db)
sys.modules.setdefault('db.queries', _mock_db.queries)
sys.modules.setdefault('db.connection', _mock_db.connection)
sys.modules.setdefault('db.models', _mock_db.models)

from web.app import create_app  # noqa: E402


# ── URL path parser tests ──────────────────────────────────────────


class TestParseUserPath:
    def test_chesscom_only(self):
        assert parse_user_path("Hikaru") == ("hikaru", None)

    def test_lichess_only(self):
        assert parse_user_path("-/DrNykterstein") == (None, "drnykterstein")

    def test_both_platforms(self):
        assert parse_user_path("Hikaru/DrNykterstein") == ("hikaru", "drnykterstein")

    def test_lowercase_normalization(self):
        assert parse_user_path("UPPERCASE") == ("uppercase", None)

    def test_lichess_only_uppercase(self):
        assert parse_user_path("-/UPPER") == (None, "upper")


class TestBuildUserPath:
    def test_chesscom_only(self):
        assert build_user_path("hikaru", None) == "hikaru"

    def test_lichess_only(self):
        assert build_user_path(None, "drnykterstein") == "-/drnykterstein"

    def test_both_platforms(self):
        assert build_user_path("hikaru", "drnykterstein") == "hikaru/drnykterstein"

    def test_lowercase_normalization(self):
        assert build_user_path("HIKARU", None) == "hikaru"

    def test_no_users_raises(self):
        with pytest.raises(ValueError):
            build_user_path(None, None)


class TestRoundTrip:
    def test_chesscom_roundtrip(self):
        path = build_user_path("hikaru", None)
        assert parse_user_path(path) == ("hikaru", None)

    def test_lichess_roundtrip(self):
        path = build_user_path(None, "drnykterstein")
        assert parse_user_path(path) == (None, "drnykterstein")

    def test_both_roundtrip(self):
        path = build_user_path("hikaru", "drnykterstein")
        assert parse_user_path(path) == ("hikaru", "drnykterstein")


# ── Flask app fixture ─────────────────────────────────────────────


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# ── Landing page ───────────────────────────────────────────────────


def test_landing_page(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'Chess CoachAI' in resp.data


# ── POST /analyze validation ──────────────────────────────────────


class TestAnalyzeValidation:
    def test_no_usernames(self, client):
        resp = client.post('/analyze', data={})
        assert resp.status_code == 400
        assert b'At least one username' in resp.data

    def test_empty_usernames(self, client):
        resp = client.post('/analyze', data={
            'chesscom_username': '',
            'lichess_username': '',
        })
        assert resp.status_code == 400

    def test_invalid_chesscom_username(self, client):
        resp = client.post('/analyze', data={
            'chesscom_username': 'bad user!@#',
        })
        assert resp.status_code == 400
        assert b'Invalid Chess.com' in resp.data

    def test_invalid_lichess_username(self, client):
        resp = client.post('/analyze', data={
            'lichess_username': 'a' * 30,
        })
        assert resp.status_code == 400
        assert b'Invalid Lichess' in resp.data

    def test_username_too_long(self, client):
        resp = client.post('/analyze', data={
            'chesscom_username': 'a' * 26,
        })
        assert resp.status_code == 400

    def test_valid_username_chars(self, client):
        """Hyphens and underscores are allowed."""
        with patch('web.routes.queries') as mock_q:
            mock_q.get_latest_job.return_value = None
            mock_q.create_job.return_value = 1
            resp = client.post('/analyze', data={
                'chesscom_username': 'valid-user_123',
            })
            assert resp.status_code == 302


# ── POST /analyze redirect logic ─────────────────────────────────


class TestAnalyzeRedirects:
    @patch('web.routes.queries')
    def test_new_job_redirects_to_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        mock_q.create_job.return_value = 42

        resp = client.post('/analyze', data={
            'chesscom_username': 'hikaru',
        })
        assert resp.status_code == 302
        assert '/u/hikaru/status' in resp.headers['Location']

    @patch('web.routes.queries')
    def test_completed_recent_redirects_to_report(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'complete',
            'completed_at': datetime.now(timezone.utc) - timedelta(minutes=30),
        }

        resp = client.post('/analyze', data={
            'chesscom_username': 'hikaru',
        })
        assert resp.status_code == 302
        assert '/u/hikaru' in resp.headers['Location']
        assert '/status' not in resp.headers['Location']

    @patch('web.routes.queries')
    def test_completed_old_creates_new_job(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'complete',
            'completed_at': datetime.now(timezone.utc) - timedelta(hours=2),
        }
        mock_q.create_job.return_value = 99

        resp = client.post('/analyze', data={
            'chesscom_username': 'hikaru',
        })
        assert resp.status_code == 302
        assert '/u/hikaru/status' in resp.headers['Location']
        mock_q.create_job.assert_called_once()

    @patch('web.routes.queries')
    def test_in_progress_redirects_to_status(self, mock_q, client):
        for status in ('pending', 'fetching', 'analyzing'):
            mock_q.get_latest_job.return_value = {'status': status}
            resp = client.post('/analyze', data={
                'chesscom_username': 'hikaru',
            })
            assert resp.status_code == 302
            assert '/u/hikaru/status' in resp.headers['Location']

    @patch('web.routes.queries')
    def test_both_usernames_path(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        mock_q.create_job.return_value = 1

        resp = client.post('/analyze', data={
            'chesscom_username': 'Hikaru',
            'lichess_username': 'DrNykterstein',
        })
        assert resp.status_code == 302
        assert '/u/hikaru/drnykterstein/status' in resp.headers['Location']

    @patch('web.routes.queries')
    def test_lichess_only_path(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        mock_q.create_job.return_value = 1

        resp = client.post('/analyze', data={
            'lichess_username': 'DrNykterstein',
        })
        assert resp.status_code == 302
        assert '/u/-/drnykterstein/status' in resp.headers['Location']


# ── GET /u/{path} ────────────────────────────────────────────────


class TestUserReport:
    @patch('web.routes.queries')
    def test_no_job_redirects_to_landing(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        resp = client.get('/u/hikaru')
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/')

    @patch('web.routes.load_endgames_data')
    @patch('web.routes.load_openings_data')
    @patch('web.routes.queries')
    def test_complete_shows_report(self, mock_q, mock_openings, mock_endgames,
                                   client):
        mock_q.get_latest_job.return_value = {'status': 'complete'}
        mock_openings.return_value = {
            'username': 'hikaru',
            'chesscom_user': 'hikaru',
            'lichess_user': None,
            'items': [],
            'groups': [],
            'total_games_analyzed': 0,
            'avg_eval_loss': 0,
            'theory_knowledge_pct': 0,
            'accuracy_pct': 0,
            'new_games_analyzed': 0,
        }
        mock_endgames.return_value = {'endgame_count': 0}
        resp = client.get('/u/hikaru')
        assert resp.status_code == 200
        assert b'Chess Coach' in resp.data

    @patch('web.routes.queries')
    def test_in_progress_redirects_to_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {'status': 'analyzing'}
        resp = client.get('/u/hikaru')
        assert resp.status_code == 302
        assert '/u/hikaru/status' in resp.headers['Location']


# ── GET /u/{path}/status/json ────────────────────────────────────


class TestStatusJson:
    @patch('web.routes.queries')
    def test_not_found(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        resp = client.get('/u/hikaru/status/json')
        assert resp.status_code == 404
        assert resp.get_json()['status'] == 'not_found'

    @patch('web.routes.queries')
    def test_returns_job_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'analyzing',
            'progress_pct': 45,
            'total_games': 200,
            'message': 'Analyzing game 90 of 200...',
        }
        resp = client.get('/u/hikaru/status/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'analyzing'
        assert data['progress_pct'] == 45
        assert data['total_games'] == 200
        assert data['message'] == 'Analyzing game 90 of 200...'

    @patch('web.routes.queries')
    def test_lichess_user_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'pending',
            'progress_pct': 0,
            'total_games': 0,
            'message': '',
        }
        resp = client.get('/u/-/drnykterstein/status/json')
        assert resp.status_code == 200
        mock_q.get_latest_job.assert_called_with(
            chesscom_user=None,
            lichess_user='drnykterstein',
        )
