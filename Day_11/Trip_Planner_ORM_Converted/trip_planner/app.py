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
    Browser --> Flask route (this file) --> ORM models/session --> MySQL tables
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

from sqlalchemy import (CheckConstraint, ForeignKey, Index, String, Integer, Date, Time,
                        Numeric, TIMESTAMP, func, select, text, inspect, URL)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask_sqlalchemy import SQLAlchemy
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

    SQLAlchemy's MySQL dialect normally returns ``datetime.time`` for TIME
    columns. The filter also handles timedelta and strings so legacy values and
    form values remain display-safe.

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
# 2. DATABASE: FLASK-SQLALCHEMY ORM MODELS + INITIALIZATION
# =============================================================================
# Flask-SQLAlchemy manages the SQLAlchemy engine and request-scoped sessions.
# URL.create safely handles passwords containing characters such as @ or #.
db = SQLAlchemy()


class User(db.Model):
    """ORM model for registered accounts in the ``users`` table."""
    __tablename__ = "users"

    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(80), nullable=False, unique=True)
    password_hash = db.Column(String(255), nullable=False)
    created_at = db.Column(TIMESTAMP, server_default=func.current_timestamp())

    # A user owns many trips. Database-level CASCADE preserves old behavior.
    trips = db.relationship("Trip", back_populates="owner", cascade="all, delete-orphan")


class Trip(db.Model):
    """ORM model for a user's trip, budget, dates, and optional image."""
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("budget >= 0", name="chk_trip_budget"),
        CheckConstraint("end_date >= start_date", name="chk_trip_dates"),
    )

    id = db.Column(Integer, primary_key=True)
    owner_id = db.Column(Integer, ForeignKey("users.id", name="fk_trips_owner", ondelete="CASCADE"), nullable=False)
    destination = db.Column(String(160), nullable=False)
    start_date = db.Column(Date, nullable=False)
    end_date = db.Column(Date, nullable=False)
    budget = db.Column(Numeric(12, 2), nullable=False)
    image_filename = db.Column(String(80), nullable=True)
    created_at = db.Column(TIMESTAMP, server_default=func.current_timestamp())

    owner = db.relationship("User", back_populates="trips")
    activities = db.relationship("Activity", back_populates="trip", cascade="all, delete-orphan")

    def to_dict(self):
        """Return the field mapping expected by the existing Jinja templates."""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class Activity(db.Model):
    """ORM model for a dated activity that belongs to one trip."""
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint("cost >= 0", name="chk_activity_cost"),
        Index("idx_activities_trip_date", "trip_id", "date"),
    )

    id = db.Column(Integer, primary_key=True)
    trip_id = db.Column(Integer, ForeignKey("trips.id", name="fk_activities_trip", ondelete="CASCADE"), nullable=False)
    name = db.Column(String(160), nullable=False)
    activity_date = db.Column("date", Date, nullable=False)
    time = db.Column(Time, nullable=False)
    category = db.Column(String(40), nullable=False)
    place = db.Column(String(200), nullable=False)
    cost = db.Column(Numeric(12, 2), nullable=False)
    image_filename = db.Column(String(80), nullable=True)
    created_at = db.Column(TIMESTAMP, server_default=func.current_timestamp())

    trip = db.relationship("Trip", back_populates="activities")

    def to_dict(self):
        """Return a mapping compatible with the previous raw-SQL row dictionaries."""
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "name": self.name,
            "date": self.activity_date,
            "time": self.time,
            "category": self.category,
            "place": self.place,
            "cost": self.cost,
            "image_filename": self.image_filename,
            "created_at": self.created_at,
        }


def _server_database_url():
    """Build a MySQL URL without a database, for first-time database creation."""
    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        query={"charset": "utf8mb4"},
    )


def configure_database():
    """Configure Flask-SQLAlchemy using the database values in ``.env``."""
    app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "trip_planner_db"),
        query={"charset": "utf8mb4"},
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)


# Configure the extension when this module is imported (also supports Flask CLI/tests).
configure_database()


def initialize_database():
    """Create the configured MySQL database and ORM tables if they are missing.

    Existing user/trip/activity records are preserved. Existing databases are
    inspected for the optional image columns and upgraded only when necessary.
    ORM models define the table schema; a small server-level SQL statement is
    used only to create the database before the ORM can connect to it.
    """
    from sqlalchemy import create_engine

    db_name = os.getenv("DB_NAME", "trip_planner_db")
    server_engine = create_engine(_server_database_url())
    try:
        # Database identifiers cannot be bound as query parameters. Escape
        # backticks and quote the configured identifier before executing DDL.
        safe_name = "`" + db_name.replace("`", "``") + "`"
        with server_engine.begin() as connection:
            connection.execute(text(
                f"CREATE DATABASE IF NOT EXISTS {safe_name} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            ))
    finally:
        server_engine.dispose()

    with app.app_context():
        # Create any missing tables from the ORM model definitions.
        db.create_all()
        inspector = inspect(db.engine)
        for table in ("trips", "activities"):
            if table in inspector.get_table_names():
                columns = {column["name"] for column in inspector.get_columns(table)}
                if "image_filename" not in columns:
                    # These are fixed table names from the list above, not input.
                    db.session.execute(text(
                        f"ALTER TABLE `{table}` ADD COLUMN image_filename VARCHAR(80) NULL"
                    ))
        # Older versions may have a retired place_suggestions table. Leave it
        # untouched so startup never deletes user data without explicit consent.
        db.session.commit()


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
        """Check the login session before calling the protected view."""
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
#   ORM session commit -> save the filename in trips.image_filename or
#                         activities.image_filename
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
def owned_trip(trip_id):
    """Return the trip as a template-compatible mapping only when user owns it."""
    trip = db.session.execute(
        select(Trip).where(Trip.id == trip_id, Trip.owner_id == session["user_id"])
    ).scalar_one_or_none()
    return trip.to_dict() if trip else None


def like_pattern(text_value):
    """Escape wildcard characters so destination search treats input literally."""
    escaped = text_value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def completed_trips(owner_id, search="", limit=None):
    """Return completed trips and activity totals using ORM aggregation.

    A trip is completed when its end date is earlier than today. The returned
    mappings retain the keys used by existing templates: trip fields,
    ``activity_count``, and ``total_cost``.
    """
    statement = (
        select(
            Trip.id, Trip.destination, Trip.start_date, Trip.end_date,
            Trip.budget, Trip.image_filename,
            func.count(Activity.id).label("activity_count"),
            func.coalesce(func.sum(Activity.cost), 0).label("total_cost"),
        )
        .outerjoin(Activity, Activity.trip_id == Trip.id)
        .where(Trip.owner_id == owner_id, Trip.end_date < date.today())
        .group_by(Trip.id, Trip.destination, Trip.start_date, Trip.end_date,
                  Trip.budget, Trip.image_filename)
        .order_by(Trip.end_date.desc(), Trip.id.desc())
    )
    if search:
        statement = statement.where(Trip.destination.like(like_pattern(search), escape="\\"))
    if limit:
        statement = statement.limit(int(limit))
    rows = db.session.execute(statement).mappings().all()
    return [dict(row) for row in rows]


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
        if not errors and db.session.execute(
            select(User.id).where(User.username == username)
        ).scalar_one_or_none() is not None:
            errors["username"] = "That username is already registered."
        if errors:
            return render_template("register.html", errors=errors, username=username)
        try:
            db.session.add(User(
                username=username,
                password_hash=generate_password_hash(password),
            ))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
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
        user = db.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
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
    total_cost_subquery = (
        select(func.coalesce(func.sum(Activity.cost), 0))
        .where(Activity.trip_id == Trip.id)
        .correlate(Trip)
        .scalar_subquery()
    )
    trip_rows = db.session.execute(
        select(Trip, total_cost_subquery.label("total_cost"))
        .where(Trip.owner_id == session["user_id"], Trip.end_date >= today)
        .order_by(Trip.start_date.asc(), Trip.id.desc())
    ).all()
    trips = [{**trip.to_dict(), "total_cost": total_cost} for trip, total_cost in trip_rows]
    completed_count = db.session.execute(
        select(func.count(Trip.id)).where(
            Trip.owner_id == session["user_id"], Trip.end_date < today
        )
    ).scalar_one()
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
            db.session.add(Trip(
                owner_id=session["user_id"], destination=values["destination"],
                start_date=values["start"], end_date=values["end"],
                budget=values["budget"], image_filename=image_name,
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
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
            outside_activity = db.session.execute(
                select(Activity).where(
                    Activity.trip_id == trip_id,
                    (Activity.activity_date < values["start"]) |
                    (Activity.activity_date > values["end"]),
                ).limit(1)
            ).scalar_one_or_none()
            outside = ({"id": outside_activity.id, "name": outside_activity.name,
                        "date": outside_activity.activity_date} if outside_activity else None)
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
            trip_record = db.session.execute(
                select(Trip).where(Trip.id == trip_id, Trip.owner_id == session["user_id"])
            ).scalar_one()
            trip_record.destination = values["destination"]
            trip_record.start_date = values["start"]
            trip_record.end_date = values["end"]
            trip_record.budget = values["budget"]
            trip_record.image_filename = image_name
            db.session.commit()
        except Exception:
            db.session.rollback()
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
    activity_records = db.session.execute(
        select(Activity).where(Activity.trip_id == trip_id).order_by(
            Activity.activity_date, Activity.time, Activity.id
        )
    ).scalars().all()
    activities = [activity.to_dict() for activity in activity_records]
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
            db.session.add(Activity(
                trip_id=trip_id, name=values["name"], activity_date=date.fromisoformat(values["date"]),
                time=datetime.strptime(values["time"], "%H:%M:%S").time(),
                category=values["category"], place=values["place"],
                cost=values["cost"], image_filename=image_name,
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
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
    joined = db.session.execute(
        select(Activity, Trip).join(Trip, Trip.id == Activity.trip_id).where(
            Activity.id == activity_id, Trip.owner_id == session["user_id"]
        )
    ).first()
    if joined:
        activity_record, trip_record = joined
        activity = {
            **activity_record.to_dict(), "destination": trip_record.destination,
            "start_date": trip_record.start_date, "end_date": trip_record.end_date,
            "budget": trip_record.budget,
        }
    else:
        activity = None
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
            activity_record = db.session.get(Activity, activity_id)
            if activity_record is None or activity_record.trip_id != trip["id"]:
                abort(404)
            activity_record.name = values["name"]
            activity_record.activity_date = date.fromisoformat(values["date"])
            activity_record.time = datetime.strptime(values["time"], "%H:%M:%S").time()
            activity_record.category = values["category"]
            activity_record.place = values["place"]
            activity_record.cost = values["cost"]
            activity_record.image_filename = image_name
            db.session.commit()
        except Exception:
            db.session.rollback()
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
    joined = db.session.execute(
        select(Activity, Trip).join(Trip, Trip.id == Activity.trip_id).where(
            Activity.id == activity_id, Trip.owner_id == session["user_id"]
        )
    ).first()
    activity = ({"id": joined[0].id, "trip_id": joined[0].trip_id,
                 "image_filename": joined[0].image_filename} if joined else None)
    if not activity:
        flash("Activity not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    activity_record = db.session.get(Activity, activity_id)
    if activity_record is not None and activity_record.trip_id == activity["trip_id"]:
        db.session.delete(activity_record)
        db.session.commit()
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
    owned_trip_image = db.session.execute(
        select(Trip.id).where(
            Trip.image_filename == filename, Trip.owner_id == session["user_id"]
        ).limit(1)
    ).scalar_one_or_none()
    owned_activity_image = db.session.execute(
        select(Activity.id).join(Trip, Trip.id == Activity.trip_id).where(
            Activity.image_filename == filename, Trip.owner_id == session["user_id"]
        ).limit(1)
    ).scalar_one_or_none()
    owned = owned_trip_image is not None or owned_activity_image is not None
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
    # Configure ORM once, create/upgrade tables, then start the development server.
    # Debug mode (auto-reload + interactive debugger) only when FLASK_DEBUG=1.
    check_environment()
    initialize_database()
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
