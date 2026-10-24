import os
import re
from datetime import date
from functools import wraps

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
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
    )


def valid_email(email):
    return re.fullmatch(r"[^\\s@]+@[^\\s@]+\\.[^\\s@]+", email) is not None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_event(event_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*,
               COALESCE(SUM(r.seats_requested), 0) AS booked_seats
        FROM events e
        LEFT JOIN registrations r ON e.id = r.event_id
        WHERE e.id = %s
        GROUP BY e.id
    """, (event_id,))
    event = cursor.fetchone()
    cursor.close()
    db.close()

    if event:
        event["available_seats"] = event["seat_capacity"] - int(event["booked_seats"])
        if event["available_seats"] < 0:
            event["available_seats"] = 0
        event["percentage"] = min(
            100,
            round((int(event["booked_seats"]) / event["seat_capacity"]) * 100)
            if event["seat_capacity"] else 0
        )
    return event


@app.route("/")
def home():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    upcoming = request.args.get("upcoming") == "1"

    db = get_db()
    cursor = db.cursor(dictionary=True)

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

    cursor.execute(query, tuple(params))
    events = cursor.fetchall()
    cursor.close()
    db.close()

    for event in events:
        event["booked_seats"] = int(event["booked_seats"])
        event["available_seats"] = max(0, event["seat_capacity"] - event["booked_seats"])
        event["percentage"] = min(
            100,
            round((event["booked_seats"] / event["seat_capacity"]) * 100)
            if event["seat_capacity"] else 0
        )

    return render_template(
        "home.html",
        events=events,
        search=search,
        category=category,
        upcoming=upcoming,
    )


@app.route("/events/create", methods=["GET", "POST"])
def create_event():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        event_date = request.form.get("event_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        venue = request.form.get("venue", "").strip()
        seat_capacity = request.form.get("seat_capacity", "").strip()
        organizer_email = request.form.get("organizer_email", "").strip()
        registration_deadline = request.form.get("registration_deadline", "").strip()
        description = request.form.get("description", "").strip()

        if not all([
            title, category, event_date, start_time, venue, seat_capacity,
            organizer_email, registration_deadline, description
        ]):
            flash("Please fill in all required fields.", "error")
            return render_template("event_form.html", event=None)

        try:
            seat_capacity = int(seat_capacity)
            if seat_capacity <= 0:
                raise ValueError
        except ValueError:
            flash("Seat capacity must be a positive number.", "error")
            return render_template("event_form.html", event=None)

        if not valid_email(organizer_email):
            flash("Please enter a valid organizer email address.", "error")
            return render_template("event_form.html", event=None)

        if registration_deadline > event_date:
            flash("Registration deadline cannot be after the event date.", "error")
            return render_template("event_form.html", event=None)

        image_filename = None
        photo = request.files.get("image")

        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Only JPG, JPEG and PNG images are allowed.", "error")
                return render_template("event_form.html", event=None)

            photo.seek(0, os.SEEK_END)
            size = photo.tell()
            photo.seek(0)

            if size > MAX_FILE_SIZE:
                flash("Image size must be 2 MB or less.", "error")
                return render_template("event_form.html", event=None)

            safe_name = secure_filename(photo.filename)
            image_filename = f"{os.urandom(8).hex()}_{safe_name}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO events
            (title, category, event_date, start_time, venue, seat_capacity,
             organizer_email, registration_deadline, description, image_filename)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            title, category, event_date, start_time, venue, seat_capacity,
            organizer_email, registration_deadline, description, image_filename
        ))
        event_id = cursor.lastrowid
        db.commit()
        cursor.close()
        db.close()

        flash("Event published successfully.", "success")
        return redirect(url_for("event_details", event_id=event_id))

    return render_template("event_form.html", event=None)


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
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        event_date = request.form.get("event_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        venue = request.form.get("venue", "").strip()
        seat_capacity = request.form.get("seat_capacity", "").strip()
        organizer_email = request.form.get("organizer_email", "").strip()
        registration_deadline = request.form.get("registration_deadline", "").strip()
        description = request.form.get("description", "").strip()

        if not all([
            title, category, event_date, start_time, venue, seat_capacity,
            organizer_email, registration_deadline, description
        ]):
            flash("Please fill in all required fields.", "error")
            return render_template("event_form.html", event=event)

        try:
            seat_capacity = int(seat_capacity)
            if seat_capacity <= 0:
                raise ValueError
        except ValueError:
            flash("Seat capacity must be a positive number.", "error")
            return render_template("event_form.html", event=event)

        if not valid_email(organizer_email):
            flash("Please enter a valid organizer email address.", "error")
            return render_template("event_form.html", event=event)

        if seat_capacity < int(event["booked_seats"]):
            flash(
                f"Seat capacity cannot be lower than {event['booked_seats']} seats already booked.",
                "error"
            )
            return render_template("event_form.html", event=event)

        if registration_deadline > event_date:
            flash("Registration deadline cannot be after the event date.", "error")
            return render_template("event_form.html", event=event)

        image_filename = event["image_filename"]
        photo = request.files.get("image")

        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Only JPG, JPEG and PNG images are allowed.", "error")
                return render_template("event_form.html", event=event)

            photo.seek(0, os.SEEK_END)
            size = photo.tell()
            photo.seek(0)

            if size > MAX_FILE_SIZE:
                flash("Image size must be 2 MB or less.", "error")
                return render_template("event_form.html", event=event)

            safe_name = secure_filename(photo.filename)
            new_filename = f"{os.urandom(8).hex()}_{safe_name}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], new_filename))

            if image_filename:
                old_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)

            image_filename = new_filename

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE events
            SET title=%s, category=%s, event_date=%s, start_time=%s,
                venue=%s, seat_capacity=%s, organizer_email=%s,
                registration_deadline=%s, description=%s, image_filename=%s
            WHERE id=%s
        """, (
            title, category, event_date, start_time, venue, seat_capacity,
            organizer_email, registration_deadline, description,
            image_filename, event_id
        ))
        db.commit()
        cursor.close()
        db.close()

        flash("Event updated successfully.", "success")
        return redirect(url_for("event_details", event_id=event_id))

    return render_template("event_form.html", event=event)


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

        if not all([full_name, email, mobile, seats_requested]):
            flash("Please fill in all required fields.", "error")
            return render_template("register.html", event=event)

        if not mobile.isdigit() or len(mobile) != 10:
            flash("Mobile number must contain exactly 10 digits.", "error")
            return render_template("register.html", event=event)

        if not valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html", event=event)

        try:
            seats_requested = int(seats_requested)
        except ValueError:
            seats_requested = 0

        if seats_requested not in (1, 2):
            flash("You can request only 1 or 2 seats.", "error")
            return render_template("register.html", event=event)

        if event["available_seats"] < seats_requested:
            flash("The requested number of seats is not available.", "error")
            return render_template("register.html", event=event)

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT id FROM registrations WHERE event_id=%s AND email=%s",
            (event_id, email)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.close()
            db.close()
            flash("This email is already registered for this event.", "error")
            return render_template("register.html", event=event)

        cursor.execute("""
            INSERT INTO registrations
            (event_id, full_name, email, mobile, seats_requested)
            VALUES (%s, %s, %s, %s, %s)
        """, (event_id, full_name, email, mobile, seats_requested))

        db.commit()
        cursor.close()
        db.close()

        flash("Registration confirmed successfully.", "success")
        return redirect(url_for("event_details", event_id=event_id))

    return render_template("register.html", event=event)


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    event = get_event(event_id)

    if not event:
        return jsonify({"error": "Event not found."}), 404

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM events WHERE id=%s", (event_id,))
    db.commit()
    cursor.close()
    db.close()

    if event["image_filename"]:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], event["image_filename"])
        if os.path.exists(image_path):
            os.remove(image_path)

    return jsonify({
        "message": "Event deleted successfully.",
        "redirect_url": url_for("home")
    })


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Uploaded file is too large."}), 413


if __name__ == "__main__":
    app.run(debug=True)
