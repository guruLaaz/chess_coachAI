"""Flask application factory."""

import logging
import os

from flask import Flask

from config import setup_logging

logger = logging.getLogger(__name__)


def create_app():
    setup_logging()

    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

    from web.routes import register_routes
    register_routes(app)

    logger.info("Flask app created")
    return app
