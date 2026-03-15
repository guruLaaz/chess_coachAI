"""Flask route definitions for Chess CoachAI."""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, date

from flask import redirect, render_template, request, jsonify, Response, abort, send_from_directory

from web.utils import parse_user_path, build_user_path
from web.reports import (
    load_openings_data, load_endgames_data, load_endgames_all_data,
    render_board_svg,
)
from db import queries

logger = logging.getLogger(__name__)

# Validation pattern: alphanumeric, underscores, hyphens
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
MAX_USERNAME_LEN = 25


def validate_username(username):
    """Return True if username is valid (or empty)."""
    if not username:
        return True
    return (len(username) <= MAX_USERNAME_LEN
            and USERNAME_PATTERN.match(username) is not None)


def check_username_exists(platform, username):
    """Check if a username exists on the given platform.

    Returns True if the account exists, False if it doesn't (404),
    or True on network errors (fail open to avoid blocking users).
    """
    if platform == 'chesscom':
        url = f"https://api.chess.com/pub/player/{username}"
    elif platform == 'lichess':
        url = f"https://lichess.org/api/user/{username}"
    else:
        return True

    req = urllib.request.Request(url, headers={'User-Agent': 'chess_coachAI/1.0'})
    try:
        urllib.request.urlopen(req, timeout=5)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        # Other HTTP errors — fail open
        logger.warning("Unexpected HTTP %d checking %s user '%s'", e.code, platform, username)
        return True
    except Exception:
        logger.warning("Network error checking %s user '%s'", platform, username, exc_info=True)
        return True


def register_routes(app):
    """Register all routes on the Flask app."""

    @app.route('/analyze', methods=['POST'])
    def analyze():
        wants_json = 'application/json' in request.headers.get('Accept', '')

        if wants_json:
            json_data = request.get_json(silent=True) or {}
            chesscom = (json_data.get('chesscom_username') or '').strip()
            lichess = (json_data.get('lichess_username') or '').strip()
        else:
            chesscom = (request.form.get('chesscom_username') or '').strip()
            lichess = (request.form.get('lichess_username') or '').strip()

        logger.info("Analysis requested: chesscom=%s lichess=%s (ip=%s ua=%s)",
                     chesscom or '-', lichess or '-',
                     request.remote_addr, request.headers.get('User-Agent', '-'))

        # Validate: at least one must be non-empty
        if not chesscom and not lichess:
            logger.warning("Analysis rejected: no username provided")
            if wants_json:
                return jsonify({'error_keys': [{'key': 'error_no_username'}]}), 400
            return 'At least one username is required.', 400

        # Validate format
        if not validate_username(chesscom):
            logger.warning("Invalid Chess.com username: %s", chesscom)
            error_keys = [{'key': 'error_invalid_username', 'platform': 'Chess.com', 'username': chesscom}]
            if wants_json:
                return jsonify({'error_keys': error_keys}), 400
            return render_template(
                'landing.html',
                error_keys=error_keys,
                chesscom_value=chesscom, lichess_value=lichess,
            ), 400
        if not validate_username(lichess):
            logger.warning("Invalid Lichess username: %s", lichess)
            error_keys = [{'key': 'error_invalid_username', 'platform': 'Lichess', 'username': lichess}]
            if wants_json:
                return jsonify({'error_keys': error_keys}), 400
            return render_template(
                'landing.html',
                error_keys=error_keys,
                chesscom_value=chesscom, lichess_value=lichess,
            ), 400

        # Verify accounts actually exist before queueing
        error_keys = []
        if chesscom and not check_username_exists('chesscom', chesscom):
            error_keys.append({'key': 'error_account_not_found', 'platform': 'Chess.com', 'username': chesscom})
        if lichess and not check_username_exists('lichess', lichess):
            error_keys.append({'key': 'error_account_not_found', 'platform': 'Lichess', 'username': lichess})
        if error_keys:
            logger.warning("Account validation failed: %s",
                           '; '.join(e['platform'] + ':' + e['username'] for e in error_keys))
            if wants_json:
                return jsonify({'error_keys': error_keys}), 400
            return render_template('landing.html', error_keys=error_keys,
                                   chesscom_value=chesscom, lichess_value=lichess)

        chesscom_lower = chesscom.lower() if chesscom else None
        lichess_lower = lichess.lower() if lichess else None
        user_path = build_user_path(chesscom_lower, lichess_lower)

        # Check for existing job
        job = queries.get_latest_job(
            chesscom_user=chesscom_lower,
            lichess_user=lichess_lower,
        )

        if job:
            if job['status'] == 'complete' and job.get('completed_at'):
                age = datetime.now(timezone.utc) - job['completed_at']
                if age.total_seconds() < 3600:
                    logger.info("Reusing recent complete job %s for %s (age %ds)",
                                job['id'], user_path, int(age.total_seconds()))
                    if wants_json:
                        return jsonify({'redirect': f'/u/{user_path}'}), 200
                    return redirect(f'/u/{user_path}')

            if job['status'] in ('pending', 'fetching', 'analyzing'):
                logger.info("Job %s already in progress for %s (status=%s)",
                            job['id'], user_path, job['status'])
                if wants_json:
                    return jsonify({'redirect': f'/u/{user_path}/status'}), 200
                return redirect(f'/u/{user_path}/status')

        # Create new job and dispatch
        job_id = queries.create_job(
            chesscom_user=chesscom_lower,
            lichess_user=lichess_lower,
        )
        logger.info("Created job %s for %s", job_id, user_path)

        try:
            from worker.tasks import analyze_user
            analyze_user.apply_async(
                args=[job_id, chesscom_lower, lichess_lower],
                task_id=f"job-{job_id}",
            )
            logger.info("Dispatched Celery task for job %s", job_id)
        except Exception:
            logger.error("Failed to dispatch task for job %s", job_id, exc_info=True)

        if wants_json:
            return jsonify({'redirect': f'/u/{user_path}/status'}), 200
        return redirect(f'/u/{user_path}/status')

    @app.route('/u/<path:user_path>/api/render-boards', methods=['POST'])
    def render_boards(user_path):
        specs = request.get_json()
        results = []
        for s in specs:
            svg = render_board_svg(
                s['fen'], s.get('move'), s['color'],
                s.get('arrow_color', ''))
            results.append(svg)
        return jsonify(results)

    @app.route('/u/<path:user_path>/status/json')
    def status_json(user_path):
        chesscom, lichess = parse_user_path(user_path)

        job = queries.get_latest_job(
            chesscom_user=chesscom,
            lichess_user=lichess,
        )

        if not job:
            return jsonify({'status': 'not_found'}), 404

        data = {
            'status': job['status'],
            'progress_pct': job.get('progress_pct', 0),
            'total_games': job.get('total_games', 0),
            'message': job.get('message') or '',
            'error_message': job.get('error_message') or '',
        }

        if job['status'] == 'pending':
            position, total = queries.get_queue_position(job['id'])
            data['queue_position'] = position
            data['queue_total'] = total

        # Include elapsed/total duration
        created = job.get('created_at')
        completed = job.get('completed_at')
        if created:
            from datetime import datetime, timezone
            now = completed or datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            elapsed = int((now - created).total_seconds())
            data['elapsed_seconds'] = elapsed

        return jsonify(data)

    @app.route('/u/<path:user_path>/status/cancel', methods=['POST'])
    def status_cancel(user_path):
        """Cancel a pending job when the user leaves the status page."""
        chesscom, lichess = parse_user_path(user_path)
        job = queries.get_latest_job(
            chesscom_user=chesscom,
            lichess_user=lichess,
        )
        if job and job['status'] == 'pending':
            if queries.cancel_job(job['id']):
                # Revoke the Celery task so it doesn't run as a ghost
                try:
                    from worker.celery_app import app as celery_app
                    celery_app.control.revoke(f"job-{job['id']}", terminate=False)
                except Exception:
                    logger.warning("Could not revoke Celery task for job %s", job['id'])
                logger.info("User left status page, cancelled pending job %s for %s",
                            job['id'], user_path)
        return '', 204

    # ── Feedback ──────────────────────────────────────────────────────

    @app.route('/api/feedback', methods=['POST'])
    def submit_feedback():
        """Receive a bug report or contact form submission."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400

        fb_type = (data.get('type') or '').strip()
        email = (data.get('email') or '').strip()
        details = (data.get('details') or '').strip()
        screenshot = data.get('screenshot', '') or ''
        page_url = data.get('page_url', '') or ''
        console_logs = data.get('console_logs', '') or ''

        if fb_type not in ('bug', 'contact'):
            return jsonify({'error': 'Invalid type'}), 400
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        if not details:
            return jsonify({'error': 'Details are required'}), 400

        queries.create_feedback(
            type=fb_type, email=email, details=details,
            screenshot=screenshot, page_url=page_url,
            console_logs=console_logs,
        )
        logger.info("Feedback submitted: type=%s email=%s", fb_type, email)
        return jsonify({'ok': True}), 201

    # ── Admin ────────────────────────────────────────────────────────

    @app.route('/admin/jobs/<int:job_id>/logs')
    def admin_job_logs(job_id):
        """Return log lines for a specific job as JSON."""
        logs = queries.get_job_logs(job_id)
        for log in logs:
            if log.get('logged_at'):
                log['logged_at'] = log['logged_at'].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify(logs)

    @app.route('/admin/logs/flask')
    def admin_flask_logs():
        """Return recent Flask server logs from in-memory ring buffer."""
        from config import memory_log_handler
        level = request.args.get('level', '').upper() or None
        limit = min(int(request.args.get('limit', '200')), 500)
        logs = memory_log_handler.get_logs(level=level, limit=limit)
        return jsonify(logs)

    # ── JSON API endpoints ──────────────────────────────────────────

    def _serialize(obj):
        """JSON serializer for objects not handled by default."""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, '_asdict'):
            return obj._asdict()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _json_response(data, status=200):
        """Return a JSON Response with proper content-type."""
        body = json.dumps(data, default=_serialize)
        return Response(body, status=status, content_type='application/json')

    def _get_job_or_redirect(user_path, chesscom, lichess):
        """Check job status, return (job, None) or (None, redirect_dict)."""
        job = queries.get_latest_job(
            chesscom_user=chesscom,
            lichess_user=lichess,
        )
        if not job:
            return None, {'redirect': '/'}
        if job['status'] in ('pending', 'fetching', 'analyzing'):
            return None, {'redirect': f'/u/{user_path}/status'}
        if job['status'] == 'failed':
            return None, {'redirect': f'/u/{user_path}/status'}
        if job['status'] != 'complete':
            return None, {'redirect': '/'}
        return job, None

    @app.route('/api/report/openings/<path:user_path>')
    def api_openings(user_path):
        chesscom, lichess = parse_user_path(user_path)
        job, redir = _get_job_or_redirect(user_path, chesscom, lichess)
        if redir:
            return _json_response(redir)
        if job.get('total_games', 0) == 0:
            return _json_response({
                'no_games': True,
                'chesscom_user': chesscom,
                'lichess_user': lichess,
            })
        data = load_openings_data(chesscom, lichess)
        data['user_path'] = user_path
        data['filter_eco'] = None
        data['filter_color'] = None
        eg_data = load_endgames_data(chesscom, lichess)
        data['endgame_count'] = eg_data['endgame_count']
        return _json_response(data)

    @app.route('/api/report/openings/<path:user_path>/<eco>/<color>')
    def api_openings_filtered(user_path, eco, color):
        chesscom, lichess = parse_user_path(user_path)
        job, redir = _get_job_or_redirect(user_path, chesscom, lichess)
        if redir:
            return _json_response(redir)
        if job.get('total_games', 0) == 0:
            return _json_response({
                'no_games': True,
                'chesscom_user': chesscom,
                'lichess_user': lichess,
            })
        data = load_openings_data(chesscom, lichess)
        data['items'] = [
            item for item in data['items']
            if item['eco_code'] == eco and item['color'] == color
        ]
        data['user_path'] = user_path
        data['filter_eco'] = eco
        data['filter_color'] = color
        eg_data = load_endgames_data(chesscom, lichess)
        data['endgame_count'] = eg_data['endgame_count']
        return _json_response(data)

    @app.route('/api/report/endgames/<path:user_path>')
    def api_endgames(user_path):
        chesscom, lichess = parse_user_path(user_path)
        job, redir = _get_job_or_redirect(user_path, chesscom, lichess)
        if redir:
            return _json_response(redir)
        if job.get('total_games', 0) == 0:
            return _json_response({
                'no_games': True,
                'chesscom_user': chesscom,
                'lichess_user': lichess,
            })
        data = load_endgames_data(chesscom, lichess)
        openings_data = load_openings_data(chesscom, lichess)
        data['groups'] = openings_data['groups']
        data['total'] = len(openings_data['items'])
        data['user_path'] = user_path
        return _json_response(data)

    @app.route('/api/report/endgames-all/<path:user_path>')
    def api_endgames_all(user_path):
        chesscom, lichess = parse_user_path(user_path)
        job, redir = _get_job_or_redirect(user_path, chesscom, lichess)
        if redir:
            return _json_response(redir)
        defn = request.args.get('def', 'minor-or-queen')
        eg_type = request.args.get('type', '')
        balance = request.args.get('balance', '')
        data = load_endgames_all_data(chesscom, lichess, defn, eg_type,
                                       balance)
        data['user_path'] = user_path
        return _json_response(data)

    @app.route('/api/admin/jobs')
    def api_admin_jobs():
        jobs = queries.get_all_jobs(limit=200)
        return _json_response({'jobs': jobs})

    @app.route('/api/admin/feedback')
    def api_admin_feedback():
        entries = queries.get_all_feedback(limit=200)
        return _json_response({'entries': entries})

    # ── Vue SPA ─────────────────────────────────────────────────────
    # These must be registered AFTER all API routes so that specific
    # Flask routes take priority over the catch-all.

    @app.route('/assets/<path:filename>')
    def vue_assets(filename):
        return send_from_directory(
            os.path.join(app.root_path, '..', 'static', 'dist', 'assets'),
            filename,
        )

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        # If the path looks like an API route but didn't match any
        # registered endpoint above, return 404 instead of the SPA.
        if path.startswith(('api/', 'analyze')):
            abort(404)
        return send_from_directory(
            os.path.join(app.root_path, '..', 'static', 'dist'),
            'index.html',
        )

