"""Top-level entry point for the Chess CoachAI web application."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fetchers"))

from web.app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
