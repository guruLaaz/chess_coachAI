"""Flask application factory."""

import os

from flask import Flask


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

    from web.routes import register_routes
    register_routes(app)

    return app
