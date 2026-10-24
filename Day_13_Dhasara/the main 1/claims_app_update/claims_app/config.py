"""Settings. Edit the 4 DB_* lines below (or set the same names as environment variables)."""
import os

from sqlalchemy.engine import URL

DB_USER = os.environ.get("DB_USER", "root")            # your MySQL username
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Chinna@9999")        # your MySQL password (any characters, even @ or #)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "claims_db")       # create it first: CREATE DATABASE claims_db;


def database_url():
    """Build the DB connection URL.
    Why: one place decides SQLite (tests/dev via DATABASE_URL) vs MySQL (default), and URL.create safely escapes odd password characters.
    Links: evaluated once at import by Config.SQLALCHEMY_DATABASE_URI; tests bypass it through create_app overrides.
    """
    return os.environ.get("DATABASE_URL") or URL.create(
        "mysql+pymysql", username=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)


class Config:
    """Flask settings; SECRET_KEY comes from the environment (run.py sets a dev default)."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = database_url()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
