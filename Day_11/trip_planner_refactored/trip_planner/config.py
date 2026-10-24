"""
config.py - SETTINGS AND ENVIRONMENT SETUP
==========================================

WHAT THIS FILE DOES
    Holds every setting the app needs in ONE place: where the database lives,
    the secret key, the upload folder, and a few limits. Nothing in this file
    runs any logic; it is just a list of settings.

WHY IT IS A SEPARATE FILE
    If you ever need to change the database (for example its password or host)
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

MySQL
    A database that runs as a separate SERVER program on your computer (or a
    remote machine). The app logs in to it with a user name and password.
    Analogy: an office building with a receptionist - you must be let in, but
    many people can work there at once.

Database connection (a.k.a. "connection string" / "URI")
    A one-line address that tells the app WHICH database to open and HOW,
    like a postal address:   dialect://user:password@host:port/database_name
    Ours looks like:         mysql+pymysql://root:secret@localhost:3306/trip_planner_db

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

from sqlalchemy.engine import URL

# The folder that contains this file. Building paths from it means the app
# works no matter which folder you launch Python from.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """All application settings. Flask reads the UPPERCASE attributes."""

    # ------------------------------------------------------------------
    # 1. DATABASE CONNECTION (MySQL)
    # ------------------------------------------------------------------
    # EDIT THE FOUR VALUES BELOW (or set them as environment variables, which
    # win over the defaults written here):
    #     DB_HOST      where MySQL runs            (default: localhost)
    #     DB_PORT      MySQL port                  (default: 3306)
    #     DB_USER      your MySQL user             (default: root)
    #     DB_PASSWORD  that user's password        (default: change-me)
    #     DB_NAME      database to use             (default: trip_planner_db)
    # The database itself is created for you on first start (see app.py).
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "Chinna@9999")
    DB_NAME = os.environ.get("DB_NAME", "trip_planner_db")

    # URL.create() builds the connection address safely: passwords containing
    # characters such as @ # / need no manual escaping.
    # "mysql+pymysql" = "talk to MySQL using the PyMySQL driver".
    SQLALCHEMY_DATABASE_URI = URL.create(
        "mysql+pymysql", username=DB_USER, password=DB_PASSWORD,
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        query={"charset": "utf8mb4"},      # full Unicode support (accents, emoji)
    )
    # ADVANCED: set DATABASE_URL to a complete address to override all of the
    # above (any database SQLAlchemy supports), e.g. sqlite:///test.db
    if os.environ.get("DATABASE_URL"):
        SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
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
