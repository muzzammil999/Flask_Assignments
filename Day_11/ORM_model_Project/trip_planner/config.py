"""
config.py - SETTINGS AND ENVIRONMENT SETUP
==========================================

WHAT THIS FILE DOES
    Holds every setting the app needs in ONE place: where the database lives,
    the secret key, the upload folder, and a few limits. Nothing in this file
    runs any logic; it is just a list of settings.

WHY IT IS A SEPARATE FILE
    If you ever need to change the database (for example from SQLite to MySQL)
    you only edit this file. app.py and models.py never need to change.

HOW IT IS USED
    app.py does:   app.config.from_object(Config)
    Flask then copies every UPPERCASE name in the Config class below into
    `app.config`, where Flask and Flask-SQLAlchemy read them.

--------------------------------------------------------------------------
KEY TERMS USED IN THIS FILE  (plain-English definitions + analogies)
--------------------------------------------------------------------------
Database
    An organised store of data that lives on disk and survives restarts.
    Analogy: a filing cabinet. Each drawer is a *table* (users, trips,
    activities) and each folder inside a drawer is a *row*.

SQLite
    A complete database that is just ONE FILE (trip_planner.db) and needs no
    server or password. Python already includes it.
    Analogy: a notebook you carry with you, instead of an office building
    with a receptionist (which is what MySQL/PostgreSQL are like).

Database connection (a.k.a. "connection string" / "URI")
    A one-line address that tells the app WHICH database to open and HOW,
    like a postal address:   dialect://user:password@host/database_name
    For SQLite the "address" is just a file path:   sqlite:///path/to/file.db

Environment variable
    A setting stored OUTSIDE your code, in your terminal/computer, e.g.
    `set SECRET_KEY=abc` (Windows) or `export SECRET_KEY=abc` (Mac/Linux).
    Analogy: a sticky note on the office door; the code reads the note, so
    secrets (passwords) never have to be written inside the source files.

Secret key
    A long random string Flask uses to sign the "session" cookie so users
    cannot forge it. Analogy: the unique stamp on a wax seal.
"""

import os
import warnings

from sqlalchemy.exc import SAWarning

# The folder that contains this file. Building paths from it means the app
# works no matter which folder you launch Python from.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# SQLite stores money (Numeric) columns as floating-point numbers and SQLAlchemy
# prints a harmless warning about it on every start. Money is rounded to 2
# decimals before it is saved, so we hide that one specific warning. (MySQL and
# PostgreSQL keep exact decimals and never show it.)
warnings.filterwarnings("ignore", message=".*Dialect sqlite.*Decimal.*", category=SAWarning)


class Config:
    """All application settings. Flask reads the UPPERCASE attributes."""

    # ------------------------------------------------------------------
    # 1. DATABASE CONNECTION
    # ------------------------------------------------------------------
    # DEFAULT: a SQLite file next to this code. Works instantly, zero setup.
    #
    # TO USE MYSQL INSTEAD: install PyMySQL (pip install PyMySQL), create an
    # empty database (CREATE DATABASE trip_planner_db;) and set the variable
    #   DATABASE_URL=mysql+pymysql://root:your_password@localhost/trip_planner_db
    # (if the password has symbols like @ or #, URL-encode them: @ -> %40)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "trip_planner.db"),
    )
    # Turn off an old feature that watches every object change (wastes memory).
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ------------------------------------------------------------------
    # 2. SECURITY
    # ------------------------------------------------------------------
    # Signs the login/session cookie. The fallback is ONLY for local learning;
    # before deploying, set a real one:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
    SESSION_COOKIE_HTTPONLY = True   # JavaScript cannot read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"  # cookie is not sent on cross-site POSTs

    # ------------------------------------------------------------------
    # 3. PHOTO UPLOADS
    # ------------------------------------------------------------------
    # Photos are saved here (outside /static, so the app can check who owns a
    # photo before showing it).
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_IMAGE_BYTES = 5 * 1024 * 1024        # one photo: 5 MB
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024     # whole request: Flask rejects bigger ones (HTTP 413)

    # ------------------------------------------------------------------
    # 4. APP-SPECIFIC CHOICES
    # ------------------------------------------------------------------
    # The allowed activity categories (they fill the dropdown AND are checked
    # on the server).
    CATEGORIES = ["Sightseeing", "Food", "Nature", "Shopping", "Adventure",
                  "Transport", "Accommodation", "Other"]
