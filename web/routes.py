"""Flask route definitions for Chess CoachAI."""

import logging
import re
from datetime import datetime, timezone

from flask import redirect, render_template, request, jsonify, url_for

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


def register_routes(app):
    """Register all routes on the Flask app."""

    @app.route('/')
    def landing():
        return render_template('landing.html')

    @app.route('/analyze', methods=['POST'])
    def analyze():
        chesscom = (request.form.get('chesscom_username') or '').strip()
        lichess = (request.form.get('lichess_username') or '').strip()

        logger.info("Analysis requested: chesscom=%s lichess=%s (ip=%s ua=%s)",
                     chesscom or '-', lichess or '-',
                     request.remote_addr, request.headers.get('User-Agent', '-'))

        # Validate: at least one must be non-empty
        if not chesscom and not lichess:
            logger.warning("Analysis rejected: no username provided")
            return 'At least one username is required.', 400

        # Validate format
        if not validate_username(chesscom):
            logger.warning("Invalid Chess.com username: %s", chesscom)
            return f'Invalid Chess.com username: {chesscom}', 400
        if not validate_username(lichess):
            logger.warning("Invalid Lichess username: %s", lichess)
            return f'Invalid Lichess username: {lichess}', 400

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
                    return redirect(f'/u/{user_path}')

            if job['status'] in ('pending', 'fetching', 'analyzing'):
                logger.info("Job %s already in progress for %s (status=%s)",
                            job['id'], user_path, job['status'])
                return redirect(f'/u/{user_path}/status')

        # Create new job and dispatch
        job_id = queries.create_job(
            chesscom_user=chesscom_lower,
            lichess_user=lichess_lower,
        )
        logger.info("Created job %s for %s", job_id, user_path)

        try:
            from worker.tasks import analyze_user
            analyze_user.delay(job_id, chesscom_lower, lichess_lower)
            logger.info("Dispatched Celery task for job %s", job_id)
        except ImportError:
            logger.error("Worker module not available — job %s created but not dispatched", job_id)

        return redirect(f'/u/{user_path}/status')

    @app.route('/u/<path:user_path>')
    def user_report(user_path):
        chesscom, lichess = parse_user_path(user_path)

        job = queries.get_latest_job(
            chesscom_user=chesscom,
            lichess_user=lichess,
        )

        if not job:
            logger.info("No job found for %s, redirecting to landing", user_path)
            return redirect('/')

        if job['status'] == 'complete':
            logger.info("Loading report for %s (job %s)", user_path, job['id'])
            data = load_openings_data(chesscom, lichess)
            data['user_path'] = user_path
            data['page'] = 'openings'
            data['filter_eco'] = None
            data['filter_color'] = None
            # Endgame count for sidebar
            eg_data = load_endgames_data(chesscom, lichess)
            data['endgame_count'] = eg_data['endgame_count']
            return render_template('openings.html', **data)

        if job['status'] in ('pending', 'fetching', 'analyzing'):
            return redirect(f'/u/{user_path}/status')

        # Failed or unknown status
        logger.warning("Job %s has status '%s' for %s, redirecting to landing",
                        job['id'], job['status'], user_path)
        return redirect('/')

    @app.route('/u/<path:user_path>/opening/<eco>/<color>')
    def opening_detail(user_path, eco, color):
        chesscom, lichess = parse_user_path(user_path)
        data = load_openings_data(chesscom, lichess)
        # Filter items to matching eco/color
        data['items'] = [
            item for item in data['items']
            if item['eco_code'] == eco and item['color'] == color
        ]
        data['user_path'] = user_path
        data['page'] = 'openings'
        data['filter_eco'] = eco
        data['filter_color'] = color
        eg_data = load_endgames_data(chesscom, lichess)
        data['endgame_count'] = eg_data['endgame_count']
        return render_template('openings.html', **data)

    @app.route('/u/<path:user_path>/endgames')
    def endgame_summary(user_path):
        chesscom, lichess = parse_user_path(user_path)
        data = load_endgames_data(chesscom, lichess)
        # Also need openings data for sidebar group count
        openings_data = load_openings_data(chesscom, lichess)
        data['groups'] = openings_data['groups']
        data['total'] = len(openings_data['items'])
        data['user_path'] = user_path
        data['page'] = 'endgames'
        return render_template('endgames.html', **data)

    @app.route('/u/<path:user_path>/endgames/all')
    def endgame_drilldown(user_path):
        chesscom, lichess = parse_user_path(user_path)
        defn = request.args.get('def', 'minor-or-queen')
        eg_type = request.args.get('type', '')
        balance = request.args.get('balance', '')
        data = load_endgames_all_data(chesscom, lichess, defn, eg_type,
                                      balance)
        data['user_path'] = user_path
        return render_template('endgames_all.html', **data)

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

    @app.route('/u/<path:user_path>/status')
    def status_page(user_path):
        chesscom, lichess = parse_user_path(user_path)
        job = queries.get_latest_job(
            chesscom_user=chesscom,
            lichess_user=lichess,
        )

        if not job:
            return redirect('/')
        if job['status'] == 'complete':
            return redirect(f'/u/{user_path}')

        return render_template('status.html',
                               user_path=user_path,
                               chesscom_user=chesscom or '',
                               lichess_user=lichess or '',
                               initial_status=job)

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
            queries.cancel_job(job['id'])
            logger.info("User left status page, cancelled pending job %s for %s",
                        job['id'], user_path)
        return '', 204
