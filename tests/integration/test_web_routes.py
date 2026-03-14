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


# ── check_username_exists unit tests ─────────────────────────────

from web.routes import check_username_exists


class TestCheckUsernameExists:
    @patch('web.routes.urllib.request.urlopen')
    def test_returns_true_when_account_exists(self, mock_urlopen):
        mock_urlopen.return_value = MagicMock()
        assert check_username_exists('lichess', 'DrNykterstein') is True

    @patch('web.routes.urllib.request.urlopen')
    def test_returns_false_on_404(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='', code=404, msg='Not Found', hdrs=None, fp=None)
        assert check_username_exists('lichess', 'hansmoke') is False

    @patch('web.routes.urllib.request.urlopen')
    def test_fails_open_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionError("timeout")
        assert check_username_exists('chesscom', 'someuser') is True

    @patch('web.routes.urllib.request.urlopen')
    def test_fails_open_on_500(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='', code=500, msg='Server Error', hdrs=None, fp=None)
        assert check_username_exists('lichess', 'someuser') is True

    def test_unknown_platform_returns_true(self):
        assert check_username_exists('unknown', 'user') is True


# ── Flask app fixture ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_worker():
    """Prevent tests from hitting the real Celery/Redis broker."""
    with patch('worker.tasks.analyze_user') as mock_task:
        mock_task.apply_async.return_value = MagicMock()
        yield mock_task


@pytest.fixture(autouse=True)
def _mock_username_check():
    """Default: assume all usernames exist (skip real API calls)."""
    with patch('web.routes.check_username_exists', return_value=True):
        yield


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


# ── POST /analyze account existence checks ───────────────────────


class TestAnalyzeAccountExists:
    @patch('web.routes.check_username_exists', return_value=False)
    def test_invalid_lichess_shows_error(self, mock_check, client):
        resp = client.post('/analyze', data={
            'lichess_username': 'hansmoke',
        })
        assert resp.status_code == 200
        assert b'not found' in resp.data
        assert b'hansmoke' in resp.data

    @patch('web.routes.check_username_exists', return_value=False)
    def test_invalid_chesscom_shows_error(self, mock_check, client):
        resp = client.post('/analyze', data={
            'chesscom_username': 'totallynotauser999',
        })
        assert resp.status_code == 200
        assert b'not found' in resp.data

    @patch('web.routes.check_username_exists', return_value=False)
    def test_invalid_username_preserves_input(self, mock_check, client):
        resp = client.post('/analyze', data={
            'lichess_username': 'hansmoke',
        })
        assert resp.status_code == 200
        assert b'hansmoke' in resp.data

    @patch('web.routes.check_username_exists', return_value=False)
    def test_invalid_username_does_not_create_job(self, mock_check, client):
        with patch('web.routes.queries') as mock_q:
            resp = client.post('/analyze', data={
                'lichess_username': 'hansmoke',
            })
            mock_q.create_job.assert_not_called()


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
            'id': 10,
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
            mock_q.get_latest_job.return_value = {'id': 1, 'status': status}
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

    @patch('web.routes.queries')
    def test_zero_games_shows_no_games_page(self, mock_q, client):
        """Complete job with 0 games should render no_games.html."""
        mock_q.get_latest_job.return_value = {
            'status': 'complete',
            'total_games': 0,
        }
        resp = client.get('/u/hikaru')
        assert resp.status_code == 200
        assert b'No games found' in resp.data

    @patch('web.routes.queries')
    def test_failed_redirects_to_status(self, mock_q, client):
        """Failed jobs should redirect to status page (not landing)."""
        mock_q.get_latest_job.return_value = {'status': 'failed'}
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
            'id': 5,
            'status': 'pending',
            'progress_pct': 0,
            'total_games': 0,
            'message': '',
        }
        mock_q.get_queue_position.return_value = (1, 1)
        resp = client.get('/u/-/drnykterstein/status/json')
        assert resp.status_code == 200
        mock_q.get_latest_job.assert_called_with(
            chesscom_user=None,
            lichess_user='drnykterstein',
        )


# ── POST /u/{path}/status/cancel ─────────────────────────────────


class TestStatusCancel:
    @patch('web.routes.queries')
    def test_cancel_pending_job(self, mock_q, client):
        """Cancel should mark pending job as failed and revoke Celery task."""
        mock_q.get_latest_job.return_value = {
            'id': 42,
            'status': 'pending',
        }
        mock_q.cancel_job.return_value = True

        with patch('web.routes.queries.cancel_job', return_value=True) as mock_cancel:
            resp = client.post('/u/hikaru/status/cancel')

        assert resp.status_code == 204

    @patch('web.routes.queries')
    def test_cancel_nonpending_is_noop(self, mock_q, client):
        """Cancel should not affect non-pending jobs."""
        mock_q.get_latest_job.return_value = {
            'id': 42,
            'status': 'analyzing',
        }
        resp = client.post('/u/hikaru/status/cancel')
        assert resp.status_code == 204
        mock_q.cancel_job.assert_not_called()

    @patch('web.routes.queries')
    def test_cancel_no_job(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        resp = client.post('/u/hikaru/status/cancel')
        assert resp.status_code == 204


# ── POST /analyze task dispatch ──────────────────────────────────


class TestAnalyzeDispatch:
    @patch('web.routes.queries')
    def test_uses_apply_async_with_task_id(self, mock_q, _mock_worker, client):
        """Task should be dispatched with deterministic task_id."""
        mock_q.get_latest_job.return_value = None
        mock_q.create_job.return_value = 77

        resp = client.post('/analyze', data={
            'chesscom_username': 'hikaru',
        })

        _mock_worker.apply_async.assert_called_once_with(
            args=[77, 'hikaru', None],
            task_id='job-77',
        )


# ── Admin endpoints ──────────────────────────────────────────────


class TestSubmitFeedback:
    def test_submit_bug_report_success(self, client):
        with patch('web.routes.queries') as mock_q:
            mock_q.create_feedback.return_value = 1
            resp = client.post('/api/feedback',
                               json={'type': 'bug', 'email': 'a@b.com',
                                     'details': 'Broken', 'screenshot': 'data:img',
                                     'page_url': '/openings',
                                     'console_logs': '[{"ts":"t","level":"error","msg":"x"}]'})
            assert resp.status_code == 201
            assert resp.get_json()['ok'] is True
            mock_q.create_feedback.assert_called_once_with(
                type='bug', email='a@b.com', details='Broken',
                screenshot='data:img', page_url='/openings',
                console_logs='[{"ts":"t","level":"error","msg":"x"}]',
            )

    def test_submit_contact_success(self, client):
        with patch('web.routes.queries') as mock_q:
            mock_q.create_feedback.return_value = 2
            resp = client.post('/api/feedback',
                               json={'type': 'contact', 'email': 'c@d.com',
                                     'details': 'Hello!'})
            assert resp.status_code == 201
            mock_q.create_feedback.assert_called_once_with(
                type='contact', email='c@d.com', details='Hello!',
                screenshot='', page_url='', console_logs='',
            )

    def test_submit_bug_without_console_logs(self, client):
        """console_logs defaults to empty string when omitted."""
        with patch('web.routes.queries') as mock_q:
            mock_q.create_feedback.return_value = 3
            resp = client.post('/api/feedback',
                               json={'type': 'bug', 'email': 'a@b.com',
                                     'details': 'No logs'})
            assert resp.status_code == 201
            mock_q.create_feedback.assert_called_once_with(
                type='bug', email='a@b.com', details='No logs',
                screenshot='', page_url='', console_logs='',
            )

    def test_submit_feedback_missing_email(self, client):
        resp = client.post('/api/feedback',
                           json={'type': 'bug', 'details': 'No email'})
        assert resp.status_code == 400
        assert b'Email' in resp.data or b'email' in resp.data

    def test_submit_feedback_missing_details(self, client):
        resp = client.post('/api/feedback',
                           json={'type': 'bug', 'email': 'a@b.com'})
        assert resp.status_code == 400
        assert b'Details' in resp.data or b'details' in resp.data

    def test_submit_feedback_invalid_type(self, client):
        resp = client.post('/api/feedback',
                           json={'type': 'spam', 'email': 'a@b.com',
                                 'details': 'Hi'})
        assert resp.status_code == 400
        assert b'type' in resp.data.lower()

    def test_submit_feedback_invalid_json(self, client):
        resp = client.post('/api/feedback',
                           data='not json',
                           content_type='application/json')
        assert resp.status_code == 400


class TestAdminFeedback:
    @patch('web.routes.queries')
    def test_admin_feedback_page_loads(self, mock_q, client):
        mock_q.get_all_feedback.return_value = []
        resp = client.get('/admin/feedback')
        assert resp.status_code == 200
        assert b'Feedback' in resp.data

    @patch('web.routes.queries')
    def test_admin_feedback_shows_entries(self, mock_q, client):
        from datetime import datetime, timezone
        mock_q.get_all_feedback.return_value = [
            {'id': 1, 'type': 'bug', 'email': 'test@test.com',
             'details': 'Something broke', 'screenshot': '',
             'page_url': '/status', 'console_logs': '',
             'created_at': datetime(2026, 3, 13, tzinfo=timezone.utc)},
        ]
        resp = client.get('/admin/feedback')
        assert resp.status_code == 200
        assert b'test@test.com' in resp.data
        assert b'Something broke' in resp.data

    @patch('web.routes.queries')
    def test_admin_feedback_hides_logs_when_empty(self, mock_q, client):
        from datetime import datetime, timezone
        mock_q.get_all_feedback.return_value = [
            {'id': 10, 'type': 'bug', 'email': 'a@b.com',
             'details': 'No logs here', 'screenshot': '',
             'page_url': '/', 'console_logs': '[]',
             'created_at': datetime(2026, 3, 13, tzinfo=timezone.utc)},
        ]
        resp = client.get('/admin/feedback')
        assert resp.status_code == 200
        assert b'toggleLogs(10)' not in resp.data

    @patch('web.routes.queries')
    def test_admin_feedback_shows_logs_when_present(self, mock_q, client):
        from datetime import datetime, timezone
        logs = '[{"ts":"2026-03-13T10:00:00Z","level":"error","msg":"TypeError"}]'
        mock_q.get_all_feedback.return_value = [
            {'id': 11, 'type': 'bug', 'email': 'a@b.com',
             'details': 'Has logs', 'screenshot': '',
             'page_url': '/', 'console_logs': logs,
             'created_at': datetime(2026, 3, 13, tzinfo=timezone.utc)},
        ]
        resp = client.get('/admin/feedback')
        assert resp.status_code == 200
        assert b'toggleLogs(11)' in resp.data
        assert b'logs-data-11' in resp.data

    @patch('web.routes.queries')
    def test_admin_feedback_logs_not_html_escaped(self, mock_q, client):
        """Console logs with & and < must not be HTML-escaped in the JSON script tag."""
        from datetime import datetime, timezone
        logs = '[{"ts":"2026-03-13T10:00:00Z","level":"info","msg":"UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) & <test>"}]'
        mock_q.get_all_feedback.return_value = [
            {'id': 20, 'type': 'bug', 'email': 'a@b.com',
             'details': 'Escaped test', 'screenshot': '',
             'page_url': '/', 'console_logs': logs,
             'created_at': datetime(2026, 3, 13, tzinfo=timezone.utc)},
        ]
        resp = client.get('/admin/feedback')
        assert resp.status_code == 200
        # The raw JSON must appear unescaped (|safe), not as &amp; or &lt;
        assert b'&amp;' not in resp.data.split(b'logs-data-20')[1].split(b'</script>')[0]
        assert b'&lt;' not in resp.data.split(b'logs-data-20')[1].split(b'</script>')[0]


class TestAdminFlaskLogs:
    def test_returns_empty_list_initially(self, client):
        resp = client.get('/admin/logs/flask')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_captures_log_entries(self, client):
        import logging
        logging.getLogger('test.flask_logs').error('test error message')
        resp = client.get('/admin/logs/flask?level=ERROR')
        assert resp.status_code == 200
        logs = resp.get_json()
        msgs = [l['message'] for l in logs]
        assert any('test error message' in m for m in msgs)

    def test_level_filter(self, client):
        import logging
        logging.getLogger('test.flask_logs').info('info msg')
        logging.getLogger('test.flask_logs').error('error msg')
        resp = client.get('/admin/logs/flask?level=ERROR')
        logs = resp.get_json()
        levels = {l['level'] for l in logs}
        assert 'INFO' not in levels


class TestAdminJobLogs:
    @patch('web.routes.queries')
    def test_returns_logs_json(self, mock_q, client):
        mock_q.get_job_logs.return_value = [
            {'logged_at': None, 'level': 'INFO', 'message': 'Starting'},
            {'logged_at': None, 'level': 'ERROR', 'message': 'Boom'},
        ]
        resp = client.get('/admin/jobs/42/logs')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]['level'] == 'INFO'
        assert data[1]['message'] == 'Boom'

    @patch('web.routes.queries')
    def test_empty_logs(self, mock_q, client):
        mock_q.get_job_logs.return_value = []
        resp = client.get('/admin/jobs/99/logs')
        assert resp.status_code == 200
        assert resp.get_json() == []
