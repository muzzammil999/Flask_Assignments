"""
Trip Planner - a small Flask + MySQL web application.

WHAT THE APP DOES
-----------------
Registered users create private trips (destination, dates, budget, optional photo)
and add dated activities to each trip (time, category, place, estimated cost,
optional photo). The app totals activity costs against the budget and shows a
"Completed Trips" page (and home-page sample trips) for the signed-in user's own
trips whose end date has passed; each shows whether it stayed within budget.

HOW THE PIECES CONNECT (see ARCHITECTURE.md for the full map)
-------------------------------------------------------------
    Browser --> Flask route (this file) --> db_* helpers --> MySQL tables
                      |                                          users
                      +--> Jinja template (templates/*.html)     trips
                      +--> static/css/style.css, static/js/script.js   activities
                      +--> uploads/ folder (photos, via /media/<file>)

    users 1---* trips 1---* activities      (ON DELETE CASCADE on both links)

FILE LAYOUT OF THIS MODULE
--------------------------
    1. Configuration & constants
    2. Database connection + schema creation/upgrade
    3. Security helpers (CSRF, login_required)
    4. Image-upload helpers
    5. Query helpers and validators
    6. Routes (pages)
    7. Error handlers and the entry point
"""

import os
import re
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

import mysql.connector
from dotenv import load_dotenv
from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

# Read DB_* and FLASK_* settings from the project's own .env file. The path is
# explicit (next to app.py) so it works no matter which folder you start Python
# from. Copy .env.example to .env if you do not have one.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)


# =============================================================================
# 1. CONFIGURATION & CONSTANTS
# =============================================================================
app = Flask(__name__)

# SECRET_KEY signs the session cookie (login state + CSRF token). Set a long
# random FLASK_SECRET_KEY in .env; the fallback is only for quick local tests.
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True   # JavaScript cannot read the cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # not sent on cross-site POSTs
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # reject any request > 6 MB (-> 413)

# Photos are stored here (outside /static so access can be checked per owner).
UPLOAD_DIR = os.path.join(app.root_path, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # per-photo limit shown to the user
# Stored filenames are always <32 hex chars>.<ext>; anything else is refused.
IMAGE_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif|webp)$")

# Largest value that fits the DECIMAL(12,2) money columns (budget, cost).
MAX_MONEY = Decimal("9999999999.99")

# Allowed activity categories. Used to validate input AND to fill the dropdown
# in activity_form.html (passed to every template by inject_globals()).
CATEGORIES = ["Sightseeing", "Food", "Nature", "Shopping", "Adventure",
              "Transport", "Accommodation", "Other"]


def check_environment():
    """Print start-up warnings about a missing or unsafe .env configuration.

    Called once from the ``__main__`` block. It never stops the app; it only
    tells the developer what to fix.
    """
    if not os.path.exists(ENV_PATH):
        print(f"WARNING: {ENV_PATH} not found - copy .env.example to .env and edit it.")
    if os.getenv("FLASK_SECRET_KEY", "change-this-secret-key") in ("", "change-this-secret-key", "replace-with-a-long-random-string"):
        print("WARNING: set FLASK_SECRET_KEY in .env to a long random value.")
    if not os.getenv("DB_PASSWORD"):
        print("NOTE: DB_PASSWORD is empty in .env - fine only if your MySQL user has no password.")


@app.template_filter("time_hhmm")
def time_hhmm(value):
    """Format a time value as ``HH:MM`` for display and <input type="time">.

    MySQL TIME columns arrive from mysql-connector as ``datetime.timedelta``
    (e.g. ``timedelta(hours=9, minutes=30)``), whose str() is "9:30:00" - not
    valid for a time input. This filter handles timedelta, time and strings.

    Used in: templates/trip_detail.html and templates/activity_form.html, and
    called directly in edit_activity().
    """
    if value is None:
        return ""
    if hasattr(value, "strftime"):                 # datetime.time / datetime
        return value.strftime("%H:%M")
    if hasattr(value, "total_seconds"):            # datetime.timedelta
        total_minutes = int(value.total_seconds() // 60)
        return f"{(total_minutes // 60) % 24:02d}:{total_minutes % 60:02d}"
    return str(value)[:5]                          # already a "HH:MM:SS" string


# =============================================================================
# 2. DATABASE: CONNECTION + SCHEMA CREATION / UPGRADE
# =============================================================================
def _db_config(with_database=True):
    """Build mysql-connector keyword arguments from environment variables.

    ``with_database=False`` omits the database name so initialize_database() can
    connect before the database exists and create it.
    """
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "charset": "utf8mb4",  # full Unicode (accents, emoji) in names/places
    }
    if with_database:
        config["database"] = os.getenv("DB_NAME", "trip_planner_db")
    return config


def get_db():
    """Open a NEW MySQL connection. Callers (db_one/db_all/db_write) close it."""
    return mysql.connector.connect(**_db_config())


def initialize_database():
    """Create the database and tables if missing, and upgrade older databases.

    Idempotent: safe to run on every start (called from the ``__main__`` block).
    Mirrors schema.sql, so you may use either one to create the database.

    Tables created
        users        - accounts (hashed passwords only)
        trips        - owned by a user; budget + optional image_filename
        activities   - belong to a trip; cost + optional image_filename

    Upgrades applied to existing databases
        * add ``image_filename`` to trips / activities if missing
        * drop the retired ``place_suggestions`` table (it held only the old
          built-in sample places, which the app no longer uses)
    """
    connection = mysql.connector.connect(**_db_config(with_database=False))
    cursor = connection.cursor()
    try:
        db_name = os.getenv("DB_NAME", "trip_planner_db")
        # The name comes from configuration, not user input; still quote it as a
        # MySQL identifier (doubling any backtick) to be safe.
        safe_db_name = "`" + db_name.replace("`", "``") + "`"
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {safe_db_name} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE {safe_db_name}")

        cursor.execute("""CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB""")

        # trips.owner_id -> users.id : deleting a user deletes their trips.
        # CHECK constraints are a second line of defence behind validate_*().
        cursor.execute("""CREATE TABLE IF NOT EXISTS trips (
            id INT AUTO_INCREMENT PRIMARY KEY,
            owner_id INT NOT NULL,
            destination VARCHAR(160) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            budget DECIMAL(12,2) NOT NULL,
            image_filename VARCHAR(80) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_trips_owner FOREIGN KEY (owner_id)
                REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT chk_trip_budget CHECK (budget >= 0),
            CONSTRAINT chk_trip_dates CHECK (end_date >= start_date)
        ) ENGINE=InnoDB""")

        # activities.trip_id -> trips.id : deleting a trip deletes its activities.
        # `date` and `time` are quoted because they are also MySQL type names.
        cursor.execute("""CREATE TABLE IF NOT EXISTS activities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            trip_id INT NOT NULL,
            name VARCHAR(160) NOT NULL,
            `date` DATE NOT NULL,
            `time` TIME NOT NULL,
            category VARCHAR(40) NOT NULL,
            place VARCHAR(200) NOT NULL,
            cost DECIMAL(12,2) NOT NULL,
            image_filename VARCHAR(80) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_activities_trip FOREIGN KEY (trip_id)
                REFERENCES trips(id) ON DELETE CASCADE,
            CONSTRAINT chk_activity_cost CHECK (cost >= 0),
            INDEX idx_activities_trip_date (trip_id, `date`)
        ) ENGINE=InnoDB""")

        # --- Upgrades for databases created by earlier versions -------------
        for table in ("trips", "activities"):
            cursor.execute(
                """SELECT COUNT(*) FROM information_schema.columns
                   WHERE table_schema = DATABASE() AND table_name = %s
                     AND column_name = 'image_filename'""",
                (table,),
            )
            if cursor.fetchone()[0] == 0:
                # `table` is one of two fixed literals above (never user input).
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN image_filename VARCHAR(80) NULL")

        # The built-in sample places were removed from the product.
        cursor.execute("DROP TABLE IF EXISTS place_suggestions")

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


# =============================================================================
# 3. SECURITY HELPERS: CSRF PROTECTION AND LOGIN GUARD
# =============================================================================
def csrf_token():
    """Return this session's CSRF token, creating it on first use.

    Every <form method="post"> contains a hidden ``_csrf`` field with this value
    (templates call ``{{ csrf_token() }}``); check_csrf() verifies it.
    """
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.context_processor
def inject_globals():
    """Make ``csrf_token()`` and ``categories`` available in EVERY template."""
    return {"csrf_token": csrf_token, "categories": CATEGORIES}


@app.before_request
def check_csrf():
    """Reject any POST whose ``_csrf`` field does not match the session token.

    Stops other websites from silently submitting forms (e.g. delete activity)
    using a logged-in user's cookie. Failure -> HTTP 400 (see bad_request()).
    """
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        # compare_digest avoids timing differences when comparing secrets.
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400)


def login_required(view):
    """Decorator: send anonymous visitors to the login page.

    ``session["user_id"]`` is set by login() and removed by logout().
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# =============================================================================
# 4. IMAGE-UPLOAD HELPERS (used by trip and activity create/edit routes)
# =============================================================================
# Flow for every create/edit route:
#   prepare_image()  -> validate the upload (no disk writes yet)
#   resolve_image()  -> write the new file / decide the filename to store
#   db_write()       -> save the filename in trips.image_filename or
#                       activities.image_filename
#   remove_image_file() -> delete the OLD file after the DB write succeeded
def sniff_image_ext(data):
    """Identify the real image type from the file's first bytes.

    Returns "jpg", "png", "gif" or "webp", or None if it is not one of those.
    The client-supplied filename/extension is never trusted.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def prepare_image(files, form, errors):
    """Validate the optional ``image`` upload and the ``remove_image`` checkbox.

    Args:
        files:  ``request.files``
        form:   ``request.form``
        errors: the errors dict being built; ``errors["image"]`` is added on
                failure and shown by the form template.

    Returns:
        ``{"data": bytes|None, "ext": str|None, "remove": bool}``. Nothing is
        written to disk here, so rejected uploads leave no stray files.
    """
    prep = {"data": None, "ext": None, "remove": form.get("remove_image") == "1"}
    upload = files.get("image")
    if upload and upload.filename:
        data = upload.read(MAX_IMAGE_BYTES + 1)  # +1 byte detects "too big"
        if len(data) > MAX_IMAGE_BYTES:
            errors["image"] = "Image must be 5 MB or smaller."
        else:
            ext = sniff_image_ext(data)
            if ext is None:
                errors["image"] = "Upload a PNG, JPG, GIF or WEBP image."
            else:
                prep["data"], prep["ext"] = data, ext
    return prep


def store_image(prep):
    """Write validated image bytes to ``uploads/`` under a random filename.

    Random names prevent overwriting, path tricks and filename guessing.
    Returns the new filename (what gets saved in the database).
    """
    name = f"{secrets.token_hex(16)}.{prep['ext']}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as fh:
        fh.write(prep["data"])
    return name


def remove_image_file(name):
    """Delete an uploaded file; ignores None, bad names and missing files."""
    if name and IMAGE_NAME_RE.match(name):
        try:
            os.remove(os.path.join(UPLOAD_DIR, name))
        except OSError:
            pass


def resolve_image(prep, existing):
    """Decide which filename to save for this create/edit.

    Args:
        prep:     result of prepare_image()
        existing: filename currently stored (None when creating)

    Returns:
        ``(filename_or_None, new_file_was_written)``. Callers use the boolean to
        delete the new file again if the database write then fails.
        New upload -> store it; "remove" ticked -> None; otherwise keep existing.
    """
    if prep["data"] is not None:
        return store_image(prep), True
    if prep["remove"]:
        return None, False
    return existing, False


# =============================================================================
# 5. QUERY HELPERS AND VALIDATORS
# =============================================================================
def db_one(query, params=()):
    """Run a SELECT and return the first row as a dict (or None).

    Opens its own connection, uses a *buffered* cursor (so no "Unread result"
    errors) and always closes everything. Always pass user data through
    ``params`` (``%s`` placeholders) - never format it into the SQL string.
    """
    conn = get_db()
    cur = None
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute(query, params)
        return cur.fetchone()
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def db_all(query, params=()):
    """Run a SELECT and return ALL rows as a list of dicts."""
    conn = get_db()
    cur = None
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute(query, params)
        return cur.fetchall()
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def db_write(query, params=()):
    """Run an INSERT/UPDATE/DELETE, commit it, and return ``lastrowid``.

    Rolls back and re-raises on any error (e.g. IntegrityError for a duplicate
    username, handled in register()).
    """
    conn = get_db()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def owned_trip(trip_id):
    """Return the trip only if it belongs to the logged-in user, else None.

    This is the ownership check behind edit_trip, trip_detail and add_activity:
    other users' trips behave exactly like trips that do not exist.
    """
    return db_one(
        "SELECT * FROM trips WHERE id = %s AND owner_id = %s",
        (trip_id, session["user_id"]),
    )


def like_pattern(text):
    """Turn user text into a safe ``LIKE`` pattern matching it literally.

    Escapes ``\\``, ``%`` and ``_`` so typing ``%`` does not match everything.
    """
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def completed_trips(owner_id, search="", limit=None):
    """Return the user's completed trips, newest first.

    A trip is COMPLETED automatically once its end date is in the past, i.e. it
    ended yesterday or earlier (``end_date < today``). Nothing is stored or
    moved in the database - the trip simply stops matching "active" in
    my_trips() and starts matching here the next day.

    Each row has the trip columns plus ``activity_count`` and ``total_cost``
    (0 when the trip has no activities, thanks to the LEFT JOIN). Templates
    compare ``total_cost`` with ``budget`` to show a "Within budget" or
    "Over budget" badge.

    Args:
        owner_id: users.id of the signed-in user (only their trips are listed).
        search:   optional text matched against the destination.
        limit:    optional maximum number of rows (home page uses 6).

    Used by: home() and completed_trips_page().
    """
    query = """SELECT t.id, t.destination, t.start_date, t.end_date, t.budget,
                      t.image_filename,
                      COUNT(a.id) AS activity_count,
                      COALESCE(SUM(a.cost), 0) AS total_cost
               FROM trips t
               LEFT JOIN activities a ON a.trip_id = t.id
               WHERE t.owner_id = %s AND t.end_date < %s"""
    params = [owner_id, date.today()]
    if search:
        query += " AND t.destination LIKE %s"
        params.append(like_pattern(search))
    query += """ GROUP BY t.id, t.destination, t.start_date, t.end_date, t.budget,
                          t.image_filename
                 ORDER BY t.end_date DESC, t.id DESC"""
    if limit:
        query += " LIMIT %s"
        params.append(int(limit))
    return db_all(query, tuple(params))


def parse_money(raw):
    """Parse a user-typed amount into a Decimal with 2 decimal places.

    Raises ``InvalidOperation`` for blanks, text, NaN/Infinity, negatives, or
    values above MAX_MONEY (which would overflow DECIMAL(12,2)).
    """
    amount = Decimal((raw or "").strip())
    if not amount.is_finite() or amount < 0 or amount > MAX_MONEY:
        raise InvalidOperation
    return amount.quantize(Decimal("0.01"))


def validate_trip_form(form):
    """Validate the trip form (create_trip and edit_trip).

    Returns ``(values, errors)``. ``values`` holds the cleaned destination,
    start, end (dates) and budget (Decimal); ``errors`` maps field name ->
    message, shown under the field in templates/trip_form.html.
    """
    destination = form.get("destination", "").strip()
    start_raw = form.get("start_date", "")
    end_raw = form.get("end_date", "")
    budget_raw = form.get("budget", "")
    errors = {}
    try:
        start = date.fromisoformat(start_raw)
    except (ValueError, TypeError):
        start = None
        errors["start_date"] = "Enter a valid start date."
    try:
        end = date.fromisoformat(end_raw)
    except (ValueError, TypeError):
        end = None
        errors["end_date"] = "Enter a valid end date."
    try:
        budget = parse_money(budget_raw)
    except (InvalidOperation, ValueError, TypeError):
        budget = None
        errors["budget"] = "Budget must be a number from 0 to 9,999,999,999.99."
    if not destination:
        errors["destination"] = "Destination is required."
    elif len(destination) > 160:
        errors["destination"] = "Destination must be 160 characters or fewer."
    if start and end and end < start:
        errors["end_date"] = "End date must be on or after the start date."
    return {"destination": destination, "start": start, "end": end, "budget": budget}, errors


def validate_activity_form(form, trip):
    """Validate the activity form (add_activity and edit_activity).

    Args:
        form: ``request.form``
        trip: dict with ``start_date`` / ``end_date`` - the activity date must
              fall inside this range.

    Returns ``(values, errors)``; ``values["time"]`` is normalised to
    ``HH:MM:SS`` and ``values["cost"]`` is a Decimal.
    """
    values = {
        "name": form.get("name", "").strip(),
        "date": form.get("date", ""),
        "time": form.get("time", ""),
        "category": form.get("category", "").strip(),
        "place": form.get("place", "").strip(),
        "cost": None,
    }
    errors = {}
    limits = {"name": 160, "place": 200}  # match the VARCHAR sizes
    for field in ("name", "date", "time", "category", "place"):
        if not values[field]:
            errors[field] = f"{field.replace('_', ' ').capitalize()} is required."
    for field, limit in limits.items():
        if field not in errors and len(values[field]) > limit:
            errors[field] = f"{field.capitalize()} must be {limit} characters or fewer."
    if "category" not in errors and values["category"] not in CATEGORIES:
        errors["category"] = "Choose a category from the list."
    if "time" not in errors:
        parsed_time = None
        for fmt in ("%H:%M", "%H:%M:%S"):  # browsers send HH:MM (sometimes HH:MM:SS)
            try:
                parsed_time = datetime.strptime(values["time"], fmt).time()
                break
            except ValueError:
                continue
        if parsed_time is None:
            errors["time"] = "Enter a valid time."
        else:
            values["time"] = parsed_time.strftime("%H:%M:%S")
    try:
        activity_date = date.fromisoformat(values["date"])
    except (ValueError, TypeError):
        activity_date = None
        errors["date"] = "Enter a valid activity date."
    if activity_date:
        if activity_date < trip["start_date"] or activity_date > trip["end_date"]:
            errors["date"] = "Activity date must be within the trip dates."
    try:
        values["cost"] = parse_money(form.get("cost", ""))
    except (InvalidOperation, ValueError, TypeError):
        errors["cost"] = "Estimated cost must be a number from 0 to 9,999,999,999.99."
    return values, errors


# =============================================================================
# 6. ROUTES (PAGES)
# =============================================================================
# Each route lists the template it renders and the tables it touches.

@app.route("/")
def home():
    """Landing page.  Template: index.html.  Tables: trips, activities.

    Signed-in users also see up to 6 of their completed trips (the same cards
    as the Completed Trips page) as sample trips; visitors see a sign-in hint.
    """
    trips = []
    if "user_id" in session:
        trips = completed_trips(session["user_id"], limit=6)
    return render_template("index.html", trips=trips)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Create an account.  Template: register.html.  Table: users (INSERT).

    Checks username length/uniqueness and password length/confirmation; stores
    only a salted hash (generate_password_hash), never the password itself.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = {}
        if not username:
            errors["username"] = "Username is required."
        elif len(username) > 80:
            errors["username"] = "Username must be 80 characters or fewer."
        if len(password) < 8:
            errors["password"] = "Password must contain at least 8 characters."
        if password != confirm:
            errors["confirm_password"] = "Passwords do not match."
        if not errors and db_one("SELECT id FROM users WHERE username = %s", (username,)):
            errors["username"] = "That username is already registered."
        if errors:
            return render_template("register.html", errors=errors, username=username)
        try:
            db_write(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, generate_password_hash(password)),
            )
        except mysql.connector.IntegrityError:
            # Two people registered the same name at the same instant: the
            # UNIQUE constraint on users.username caught it.
            errors["username"] = "That username is already registered."
            return render_template("register.html", errors=errors, username=username)
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", errors={}, username="")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Sign in.  Template: login.html.  Table: users (SELECT).

    The same message is shown for unknown user and wrong password so attackers
    cannot discover which usernames exist. ``session.clear()`` on success
    prevents session fixation.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db_one("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("You are logged in.", "success")
            return redirect(url_for("my_trips"))
        return render_template("login.html", error="Invalid username or password.", username=username)
    return render_template("login.html", error=None, username="")


@app.route("/logout", methods=["POST"])
def logout():
    """Sign out (POST + CSRF so another site cannot log you out)."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/trips")
@login_required
def my_trips():
    """List the user's ACTIVE trips (upcoming or ongoing).
    Template: my_trips.html.  Tables: trips, activities.

    Trips whose end date has passed are not listed here; they have moved to the
    Completed Trips page (``completed_count`` feeds the link to it). A correlated
    subquery adds ``total_cost`` (sum of that trip's activities).
    """
    today = date.today()
    trips = db_all(
        """SELECT t.*,
                  COALESCE((SELECT SUM(a.cost) FROM activities a WHERE a.trip_id = t.id), 0) AS total_cost
           FROM trips t WHERE t.owner_id = %s AND t.end_date >= %s
           ORDER BY t.start_date ASC, t.id DESC""",
        (session["user_id"], today),
    )
    completed_count = db_one(
        "SELECT COUNT(*) AS n FROM trips WHERE owner_id = %s AND end_date < %s",
        (session["user_id"], today),
    )["n"]
    return render_template("my_trips.html", trips=trips, completed_count=completed_count)


@app.route("/trips/new", methods=["GET", "POST"])
@login_required
def create_trip():
    """Create a trip (with optional photo).  Template: trip_form.html.
    Table: trips (INSERT).  Static: script.js keeps end date >= start date.
    """
    if request.method == "POST":
        values, errors = validate_trip_form(request.form)
        prep = prepare_image(request.files, request.form, errors)
        if errors:
            return render_template("trip_form.html", trip=None, errors=errors, values=request.form, page_title="Create Trip")
        image_name, written = resolve_image(prep, None)
        try:
            db_write(
                "INSERT INTO trips (owner_id, destination, start_date, end_date, budget, image_filename) VALUES (%s, %s, %s, %s, %s, %s)",
                (session["user_id"], values["destination"], values["start"], values["end"], values["budget"], image_name),
            )
        except Exception:
            if written:
                remove_image_file(image_name)  # do not leave an orphan file
            raise
        flash("Trip created. Add your activities next.", "success")
        return redirect(url_for("my_trips"))
    return render_template("trip_form.html", trip=None, errors={}, values={}, page_title="Create Trip")


@app.route("/trips/<int:trip_id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(trip_id):
    """Edit a trip, replace/remove its photo.  Template: trip_form.html.
    Tables: trips (UPDATE), activities (SELECT for the date-range check).

    Refuses new dates that would leave an existing activity outside the trip.
    """
    trip = owned_trip(trip_id)
    if not trip:
        flash("Trip not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    if request.method == "POST":
        values, errors = validate_trip_form(request.form)
        if not errors:
            # Any activity outside the NEW date range blocks the change.
            outside = db_one(
                """SELECT id, name, `date` FROM activities
                   WHERE trip_id = %s AND (`date` < %s OR `date` > %s) LIMIT 1""",
                (trip_id, values["start"], values["end"]),
            )
            if outside:
                errors["date_range"] = (
                    f'Cannot change dates: activity "{outside["name"]}" on {outside["date"]} '
                    "would fall outside the new trip dates. Update or remove that activity first."
                )
        prep = prepare_image(request.files, request.form, errors)
        if errors:
            return render_template("trip_form.html", trip=trip, errors=errors, values=request.form, page_title="Edit Trip")
        image_name, written = resolve_image(prep, trip["image_filename"])
        try:
            db_write(
                "UPDATE trips SET destination=%s, start_date=%s, end_date=%s, budget=%s, image_filename=%s WHERE id=%s AND owner_id=%s",
                (values["destination"], values["start"], values["end"], values["budget"], image_name, trip_id, session["user_id"]),
            )
        except Exception:
            if written:
                remove_image_file(image_name)
            raise
        if image_name != trip["image_filename"]:
            remove_image_file(trip["image_filename"])  # old photo is now unused
        flash("Trip updated.", "success")
        return redirect(url_for("trip_detail", trip_id=trip_id))
    return render_template("trip_form.html", trip=trip, errors={}, values=trip, page_title="Edit Trip")


@app.route("/trips/<int:trip_id>")
@login_required
def trip_detail(trip_id):
    """Trip itinerary + budget panel.  Template: trip_detail.html.
    Tables: trips, activities (both SELECT).

    Activities are grouped by date; the totals are recomputed from the saved
    rows on every page load, so the budget panel is always current.
    """
    trip = owned_trip(trip_id)
    if not trip:
        flash("Trip not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    activities = db_all(
        "SELECT * FROM activities WHERE trip_id=%s ORDER BY `date`, `time`, id",
        (trip_id,),
    )
    grouped = {}  # {date: [activity, ...]} - insertion order = date order
    for activity in activities:
        grouped.setdefault(activity["date"], []).append(activity)
    total = sum((Decimal(str(a["cost"])) for a in activities), Decimal("0"))
    budget = Decimal(str(trip["budget"]))
    return render_template(
        "trip_detail.html", trip=trip, grouped_activities=grouped,
        total=total, difference=budget-total,  # negative = over budget
        is_completed=trip["end_date"] < date.today(),  # shows the "Completed" badge
    )


@app.route("/trips/<int:trip_id>/activities/new", methods=["GET", "POST"])
@login_required
def add_activity(trip_id):
    """Add an activity (with optional photo).  Template: activity_form.html.
    Table: activities (INSERT).  The trip must belong to the user.
    """
    trip = owned_trip(trip_id)
    if not trip:
        flash("Trip not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    if request.method == "POST":
        values, errors = validate_activity_form(request.form, trip)
        prep = prepare_image(request.files, request.form, errors)
        if errors:
            return render_template("activity_form.html", trip=trip, activity=None, errors=errors, values=request.form, page_title="Add Activity")
        image_name, written = resolve_image(prep, None)
        try:
            db_write(
                """INSERT INTO activities (trip_id, name, `date`, `time`, category, place, cost, image_filename)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (trip_id, values["name"], values["date"], values["time"], values["category"],
                 values["place"], values["cost"], image_name),
            )
        except Exception:
            if written:
                remove_image_file(image_name)
            raise
        flash("Activity added.", "success")
        return redirect(url_for("trip_detail", trip_id=trip_id))
    return render_template("activity_form.html", trip=trip, activity=None, errors={}, values={}, page_title="Add Activity")


@app.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
def edit_activity(activity_id):
    """Edit an activity / replace or remove its photo.  Template: activity_form.html.
    Tables: activities (UPDATE) joined to trips (ownership + date range).

    Ownership is enforced by the JOIN: the activity is only found when its trip
    belongs to the logged-in user.
    """
    activity = db_one(
        """SELECT a.id, a.trip_id, a.name, a.`date`, a.`time`, a.category, a.place, a.cost, a.image_filename,
                  t.destination, t.start_date, t.end_date, t.budget
           FROM activities a JOIN trips t ON t.id=a.trip_id
           WHERE a.id=%s AND t.owner_id=%s""",
        (activity_id, session["user_id"]),
    )
    if not activity:
        flash("Activity not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    # NOTE: activity["id"] is the ACTIVITY's id; the trip's id is activity["trip_id"].
    trip = {
        "id": activity["trip_id"],
        "destination": activity["destination"],
        "start_date": activity["start_date"],
        "end_date": activity["end_date"],
        "budget": activity["budget"],
    }
    # Pre-fill values as strings the HTML inputs accept (time -> "HH:MM").
    form_values = {
        "name": activity["name"],
        "date": activity["date"].isoformat(),
        "time": time_hhmm(activity["time"]),
        "category": activity["category"],
        "place": activity["place"],
        "cost": activity["cost"],
    }
    if request.method == "POST":
        values, errors = validate_activity_form(request.form, trip)
        prep = prepare_image(request.files, request.form, errors)
        if errors:
            return render_template("activity_form.html", trip=trip, activity=activity, errors=errors, values=request.form, page_title="Edit Activity")
        image_name, written = resolve_image(prep, activity["image_filename"])
        try:
            db_write(
                """UPDATE activities SET name=%s, `date`=%s, `time`=%s, category=%s, place=%s, cost=%s,
                          image_filename=%s
                   WHERE id=%s AND trip_id=%s""",
                (values["name"], values["date"], values["time"], values["category"],
                 values["place"], values["cost"], image_name, activity_id, trip["id"]),
            )
        except Exception:
            if written:
                remove_image_file(image_name)
            raise
        if image_name != activity["image_filename"]:
            remove_image_file(activity["image_filename"])
        flash("Activity updated.", "success")
        return redirect(url_for("trip_detail", trip_id=trip["id"]))
    return render_template("activity_form.html", trip=trip, activity=activity, errors={}, values=form_values, page_title="Edit Activity")


@app.route("/activities/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete_activity(activity_id):
    """Delete an activity and its photo file.  Table: activities (DELETE).
    POST-only (button in trip_detail.html) so a link/prefetch cannot delete.
    """
    activity = db_one(
        """SELECT a.id, a.trip_id, a.image_filename FROM activities a
           JOIN trips t ON t.id=a.trip_id
           WHERE a.id=%s AND t.owner_id=%s""",
        (activity_id, session["user_id"]),
    )
    if not activity:
        flash("Activity not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    db_write("DELETE FROM activities WHERE id=%s AND trip_id=%s", (activity_id, activity["trip_id"]))
    remove_image_file(activity["image_filename"])
    flash("Activity deleted.", "success")
    return redirect(url_for("trip_detail", trip_id=activity["trip_id"]))


@app.route("/completed")
@login_required
def completed_trips_page():
    """All of the user's completed trips (end date before today).
    Template: explore.html.  Tables: trips + activities (via completed_trips()).

    Optional ``?search=`` filters by destination. Only the signed-in user's own
    trips are ever listed, so the privacy promise of "My Trips" still holds.
    """
    search = request.args.get("search", "").strip()
    trips = completed_trips(session["user_id"], search=search)
    return render_template("explore.html", trips=trips, search=search)


@app.route("/media/<filename>")
@login_required
def media(filename):
    """Serve an uploaded photo - only to the user who owns it.

    Used by every ``<img src="{{ url_for('media', filename=...) }}">`` in the
    templates. The name must match IMAGE_NAME_RE (blocks ``../`` tricks) and
    must belong to one of the user's trips or activities; otherwise 404.
    """
    if not IMAGE_NAME_RE.match(filename):
        abort(404)
    owned = db_one(
        """SELECT 1 AS ok FROM trips WHERE image_filename=%s AND owner_id=%s
           UNION
           SELECT 1 FROM activities a JOIN trips t ON t.id=a.trip_id
           WHERE a.image_filename=%s AND t.owner_id=%s""",
        (filename, session["user_id"], filename, session["user_id"]),
    )
    if not owned:
        abort(404)
    response = send_from_directory(UPLOAD_DIR, filename)
    response.headers["Cache-Control"] = "private, max-age=3600"  # browser-only cache
    response.headers["X-Content-Type-Options"] = "nosniff"       # never guess a type
    return response


# =============================================================================
# 7. ERROR HANDLERS AND ENTRY POINT  (all render templates/error.html)
# =============================================================================
@app.errorhandler(413)
def too_large(_error):
    """Request body over MAX_CONTENT_LENGTH (an oversized photo)."""
    return render_template("error.html", message="That upload is too large. Images must be 5 MB or smaller."), 413


@app.errorhandler(400)
def bad_request(_error):
    """Raised by check_csrf() when the form token is missing or wrong."""
    return render_template("error.html", message="Your session expired or the form was invalid. Please go back, refresh the page and try again."), 400


@app.errorhandler(404)
def not_found(_error):
    """Unknown URL, or a /media/ file the user does not own."""
    return render_template("error.html", message="That page could not be found."), 404


@app.errorhandler(500)
def server_error(_error):
    """Unexpected failure - most often MySQL is down or .env is wrong."""
    return render_template("error.html", message="Something went wrong. Check the Flask terminal and database configuration."), 500


if __name__ == "__main__":
    # `python app.py`: create/upgrade the database, then start the dev server.
    # Debug mode (auto-reload + interactive debugger) only when FLASK_DEBUG=1.
    check_environment()
    initialize_database()
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
