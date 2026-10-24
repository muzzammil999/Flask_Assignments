"""Run this file to start the app: `python run.py` (opens on http://127.0.0.1:5000).
For local use only: it fills in a dev SECRET_KEY if you did not set one, and creates missing tables.
"""
import os

os.environ.setdefault("SECRET_KEY", "dev-only-change-me")  # must be set before config is imported

from app import create_app
from app.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
