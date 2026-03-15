"""Tests for the status page routes and JSON endpoint."""

import sys
from unittest.mock import patch, MagicMock

import pytest

# Mock db modules before importing app (same pattern as test_web_routes.py)
_mock_db = MagicMock()
sys.modules.setdefault('db', _mock_db)
sys.modules.setdefault('db.queries', _mock_db.queries)
sys.modules.setdefault('db.connection', _mock_db.connection)
sys.modules.setdefault('db.models', _mock_db.models)

from web.app import create_app  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# ── GET /u/{path}/status (now served by SPA catch-all) ────────────


class TestStatusPage:
    """Status page HTML is now served by the Vue SPA catch-all.
    These tests verify the catch-all returns the SPA shell."""

    def test_status_path_serves_spa(self, client):
        resp = client.get('/u/hikaru/status')
        assert resp.status_code == 200
        assert b'<div id="app"></div>' in resp.data

    def test_lichess_status_path_serves_spa(self, client):
        resp = client.get('/u/-/drnykterstein/status')
        assert resp.status_code == 200
        assert b'<div id="app"></div>' in resp.data

    def test_both_users_status_path_serves_spa(self, client):
        resp = client.get('/u/hikaru/drnykterstein/status')
        assert resp.status_code == 200
        assert b'<div id="app"></div>' in resp.data


# ── GET /u/{path}/status/json ─────────────────────────────────────


class TestStatusJson:
    @patch('web.routes.queries')
    def test_not_found(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        resp = client.get('/u/hikaru/status/json')
        assert resp.status_code == 404
        assert resp.get_json()['status'] == 'not_found'

    @patch('web.routes.queries')
    def test_pending_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'id': 1,
            'status': 'pending',
            'progress_pct': 0,
            'total_games': 0,
            'message': None,
            'error_message': None,
        }
        mock_q.get_queue_position.return_value = (1, 1)
        resp = client.get('/u/hikaru/status/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'pending'
        assert data['progress_pct'] == 0
        assert data['message'] == ''
        assert data['error_message'] == ''

    @patch('web.routes.queries')
    def test_fetching_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'fetching',
            'progress_pct': 15,
            'total_games': 0,
            'message': 'Downloading games from Chess.com',
            'error_message': None,
        }
        resp = client.get('/u/hikaru/status/json')
        data = resp.get_json()
        assert data['status'] == 'fetching'
        assert data['progress_pct'] == 15

    @patch('web.routes.queries')
    def test_analyzing_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'analyzing',
            'progress_pct': 60,
            'total_games': 200,
            'message': 'Analyzing game 120 of 200...',
            'error_message': None,
        }
        resp = client.get('/u/hikaru/status/json')
        data = resp.get_json()
        assert data['status'] == 'analyzing'
        assert data['progress_pct'] == 60
        assert data['total_games'] == 200
        assert data['message'] == 'Analyzing game 120 of 200...'

    @patch('web.routes.queries')
    def test_complete_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'complete',
            'progress_pct': 100,
            'total_games': 200,
            'message': 'Done',
            'error_message': None,
        }
        resp = client.get('/u/hikaru/status/json')
        data = resp.get_json()
        assert data['status'] == 'complete'
        assert data['progress_pct'] == 100

    @patch('web.routes.queries')
    def test_failed_status(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'status': 'failed',
            'progress_pct': 30,
            'total_games': 200,
            'message': '',
            'error_message': 'Chess.com API returned 429',
        }
        resp = client.get('/u/hikaru/status/json')
        data = resp.get_json()
        assert data['status'] == 'failed'
        assert data['error_message'] == 'Chess.com API returned 429'

    @patch('web.routes.queries')
    def test_null_fields_become_empty_strings(self, mock_q, client):
        """message and error_message should be '' when None in DB."""
        mock_q.get_latest_job.return_value = {
            'id': 2,
            'status': 'pending',
            'progress_pct': 0,
            'total_games': 0,
            'message': None,
            'error_message': None,
        }
        mock_q.get_queue_position.return_value = (1, 1)
        resp = client.get('/u/hikaru/status/json')
        data = resp.get_json()
        assert data['message'] == ''
        assert data['error_message'] == ''

    @patch('web.routes.queries')
    def test_lichess_user_path_parsing(self, mock_q, client):
        mock_q.get_latest_job.return_value = {
            'id': 3,
            'status': 'pending',
            'progress_pct': 0,
            'total_games': 0,
            'message': '',
            'error_message': '',
        }
        mock_q.get_queue_position.return_value = (1, 1)
        resp = client.get('/u/-/drnykterstein/status/json')
        assert resp.status_code == 200
        mock_q.get_latest_job.assert_called_with(
            chesscom_user=None,
            lichess_user='drnykterstein',
        )
