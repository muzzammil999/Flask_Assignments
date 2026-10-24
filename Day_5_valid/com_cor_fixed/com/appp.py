import os
import re
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "community-event-secret")

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_FILE_SIZE = 2 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# Reject oversized requests early (image limit + room for the other form fields)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE + 512 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
FORM_FIELDS = [
    "title", "category", "event_date", "start_time", "venue",
    "seat_capacity", "organizer_email", "registration_deadline", "description",
]


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
    )


@contextmanager
def db_cursor(dictionary=False, commit=False):
    """Open a connection + cursor and always close them, even on errors."""
    db = get_db()
    cursor = db.cursor(dictionary=dictionary)
    try:
        yield cursor
        if commit:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def to_time(value):
    """MySQL TIME columns come back as datetime.timedelta; convert to datetime.time."""
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds()) % 86400
        return time(seconds // 3600, (seconds % 3600) // 60, seconds % 60)
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, str):
        return datetime.strptime(value, "%H:%M:%S").time()
    return value


def prepare_event(event):
    """Fix column types and add the seat-availability fields used by the templates."""
    event["start_time"] = to_time(event["start_time"])
    event["booked_seats"] = int(event["booked_seats"])
    capacity = event["seat_capacity"]
    event["available_seats"] = max(0, capacity - event["booked_seats"])
    event["percentage"] = min(100, round(event["booked_seats"] / capacity * 100)) if capacity else 0
    return event


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
def valid_email(email):
    return EMAIL_PATTERN.fullmatch(email) is not None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_event(event_id):
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT e.*,
                   COALESCE(SUM(r.seats_requested), 0) AS booked_seats
            FROM events e
            LEFT JOIN registrations r ON e.id = r.event_id
            WHERE e.id = %s
            GROUP BY e.id
        """, (event_id,))
        event = cursor.fetchone()
    return prepare_event(event) if event else None


def form_values(event=None):
    """Values shown in the event form: submitted data if any, else the event, else blank."""
    if request.method == "POST":
        values = {name: request.form.get(name, "") for name in FORM_FIELDS}
    elif event:
        values = {
            "title": event["title"],
            "category": event["category"],
            "event_date": event["event_date"].strftime("%Y-%m-%d"),
            "start_time": event["start_time"].strftime("%H:%M"),
            "venue": event["venue"],
            "seat_capacity": event["seat_capacity"],
            "organizer_email": event["organizer_email"],
            "registration_deadline": event["registration_deadline"].strftime("%Y-%m-%d"),
            "description": event["description"],
        }
    else:
        values = {name: "" for name in FORM_FIELDS}
    return values


def render_event_form(event=None):
    return render_template("event_form.html", event=event, values=form_values(event))


def read_event_form(event=None):
    """Validate the event form. Returns (data, error_message)."""
    data = {name: request.form.get(name, "").strip() for name in FORM_FIELDS}

    if not all(data.values()):
        return None, "Please fill in all required fields."

    try:
        data["seat_capacity"] = int(data["seat_capacity"])
        if data["seat_capacity"] <= 0:
            raise ValueError
    except ValueError:
        return None, "Seat capacity must be a positive number."

    if not valid_email(data["organizer_email"]):
        return None, "Please enter a valid organizer email address."

    try:
        datetime.strptime(data["event_date"], "%Y-%m-%d")
        datetime.strptime(data["registration_deadline"], "%Y-%m-%d")
        datetime.strptime(data["start_time"][:5], "%H:%M")
    except ValueError:
        return None, "Please enter a valid date and time."

    if event and data["seat_capacity"] < event["booked_seats"]:
        return None, (
            f"Seat capacity cannot be lower than {event['booked_seats']} seats already booked."
        )

    if data["registration_deadline"] > data["event_date"]:
        return None, "Registration deadline cannot be after the event date."

    return data, None


def save_image(photo):
    """Validate and save an uploaded image. Returns (filename, error_message)."""
    if not allowed_file(photo.filename):
        return None, "Only JPG, JPEG and PNG images are allowed."

    photo.seek(0, os.SEEK_END)
    size = photo.tell()
    photo.seek(0)

    if size > MAX_FILE_SIZE:
        return None, "Image size must be 2 MB or less."

    filename = f"{os.urandom(8).hex()}_{secure_filename(photo.filename)}"
    photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return filename, None


def remove_image(filename):
    if filename:
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(path):
            os.remove(path)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def home():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    upcoming = request.args.get("upcoming") == "1"

    query = """
        SELECT e.*,
               COALESCE(SUM(r.seats_requested), 0) AS booked_seats
        FROM events e
        LEFT JOIN registrations r ON e.id = r.event_id
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (e.title LIKE %s OR e.venue LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like])

    if category and category != "All categories":
        query += " AND e.category = %s"
        params.append(category)

    if upcoming:
        query += " AND e.event_date >= CURDATE()"

    query += """
        GROUP BY e.id
        ORDER BY e.event_date ASC, e.start_time ASC
    """

    with db_cursor(dictionary=True) as cursor:
        cursor.execute(query, tuple(params))
        events = [prepare_event(row) for row in cursor.fetchall()]

    return render_template(
        "home.html", events=events, search=search, category=category, upcoming=upcoming
    )


@app.route("/events/create", methods=["GET", "POST"])
def create_event():
    if request.method == "POST":
        data, error = read_event_form()
        if error:
            flash(error, "error")
            return render_event_form()

        image_filename = None
        photo = request.files.get("image")
        if photo and photo.filename:
            image_filename, error = save_image(photo)
            if error:
                flash(error, "error")
                return render_event_form()

        with db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO events
                (title, category, event_date, start_time, venue, seat_capacity,
                 organizer_email, registration_deadline, description, image_filename)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["title"], data["category"], data["event_date"], data["start_time"],
                data["venue"], data["seat_capacity"], data["organizer_email"],
                data["registration_deadline"], data["description"], image_filename,
            ))
            event_id = cursor.lastrowid

        flash("Event published successfully.", "success")
        return redirect(url_for("event_details", event_id=event_id))

    return render_event_form()


@app.route("/events/<int:event_id>")
def event_details(event_id):
    event = get_event(event_id)

    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("home"))

    return render_template("details.html", event=event)


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def edit_event(event_id):
    event = get_event(event_id)

    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        data, error = read_event_form(event)
        if error:
            flash(error, "error")
            return render_event_form(event)

        image_filename = event["image_filename"]
        photo = request.files.get("image")
        if photo and photo.filename:
            new_filename, error = save_image(photo)
            if error:
                flash(error, "error")
                return render_event_form(event)
            remove_image(image_filename)
            image_filename = new_filename

        with db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE events
                SET title=%s, category=%s, event_date=%s, start_time=%s,
                    venue=%s, seat_capacity=%s, organizer_email=%s,
                    registration_deadline=%s, description=%s, image_filename=%s
                WHERE id=%s
            """, (
                data["title"], data["category"], data["event_date"], data["start_time"],
                data["venue"], data["seat_capacity"], data["organizer_email"],
                data["registration_deadline"], data["description"], image_filename,
                event_id,
            ))

        flash("Event updated successfully.", "success")
        return redirect(url_for("event_details", event_id=event_id))

    return render_event_form(event)


@app.route("/events/<int:event_id>/register", methods=["GET", "POST"])
def register_event(event_id):
    event = get_event(event_id)

    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()
        seats_requested = request.form.get("seats_requested", "1").strip()

        def fail(message):
            flash(message, "error")
            return render_template("register.html", event=event)

        if not all([full_name, email, mobile, seats_requested]):
            return fail("Please fill in all required fields.")

        if not (mobile.isascii() and mobile.isdigit() and len(mobile) == 10):
            return fail("Mobile number must contain exactly 10 digits.")

        if not valid_email(email):
            return fail("Please enter a valid email address.")

        try:
            seats_requested = int(seats_requested)
        except ValueError:
            seats_requested = 0

        if seats_requested not in (1, 2):
            return fail("You can request only 1 or 2 seats.")

        if date.today() > event["registration_deadline"]:
            return fail("The registration deadline for this event has passed.")

        if event["available_seats"] < seats_requested:
            return fail("The requested number of seats is not available.")

        try:
            with db_cursor(commit=True) as cursor:
                cursor.execute(
                    "SELECT id FROM registrations WHERE event_id=%s AND email=%s",
                    (event_id, email),
                )
                if cursor.fetchone():
                    return fail("This email is already registered for this event.")

                cursor.execute("""
                    INSERT INTO registrations
                    (event_id, full_name, email, mobile, seats_requested)
                    VALUES (%s, %s, %s, %s, %s)
                """, (event_id, full_name, email, mobile, seats_requested))
        except mysql.connector.IntegrityError:
            # unique_event_email constraint (two submissions at the same moment)
            return fail("This email is already registered for this event.")

        flash("Registration confirmed successfully.", "success")
        return redirect(url_for("event_details", event_id=event_id))

    return render_template("register.html", event=event)


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    event = get_event(event_id)

    if not event:
        return jsonify({"error": "Event not found."}), 404

    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM events WHERE id=%s", (event_id,))

    remove_image(event["image_filename"])

    return jsonify({
        "message": "Event deleted successfully.",
        "redirect_url": url_for("home"),
    })


@app.errorhandler(413)
def too_large(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Uploaded file is too large."}), 413
    flash("Image size must be 2 MB or less.", "error")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
