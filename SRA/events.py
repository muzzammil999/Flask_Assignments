"""NEW: Community Event Manager routes (blueprint). Reuses helpers from your app.py."""
import os
import random
import re
from datetime import date, datetime, timedelta

import mysql.connector
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import MAX_PHOTO_SIZE, allowed_photo, app, get_db  # your existing code, reused

bp = Blueprint("events", __name__, url_prefix="/events")

CATEGORIES = ["Workshop", "Community", "Career"]
MESSAGES = {
    "created": "Event published successfully. Your new event now appears in the list.",
    "updated": "Event updated successfully.",
    "deleted": "Event deleted.",
    "registered": "Registration confirmed. Your seat(s) are reserved.",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- template helpers ----------
@bp.app_template_filter("dmy")
def dmy(d):
    return f"{d.day} {d.strftime('%b %Y')}" if d else ""


@bp.app_template_filter("hm12")
def hm12(t):
    # MySQL TIME comes back as timedelta
    total = int(t.total_seconds()) if isinstance(t, timedelta) else 0
    h, m = divmod(total // 60, 60)
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


@bp.app_template_filter("hm24")
def hm24(t):
    total = int(t.total_seconds()) if isinstance(t, timedelta) else 0
    h, m = divmod(total // 60, 60)
    return f"{h:02d}:{m:02d}"


# ---------- db helpers ----------
EVENT_SELECT = (
    "SELECT e.*, COALESCE(SUM(r.seats), 0) AS booked FROM events e "
    "LEFT JOIN event_registrations r ON r.event_id = e.id "
)


def fetch(sql, params=()):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def add_status(ev):
    ev["booked"] = int(ev["booked"])
    ev["available"] = max(ev["capacity"] - ev["booked"], 0)
    ev["percent"] = min(100, round(ev["booked"] * 100 / ev["capacity"])) if ev["capacity"] else 100
    ev["is_full"] = ev["available"] == 0
    today = date.today()
    ev["is_closed"] = ev["reg_deadline"] < today or ev["event_date"] < today
    return ev


def get_event(event_id):
    rows = fetch(EVENT_SELECT + "WHERE e.id = %s GROUP BY e.id", (event_id,))
    if not rows:
        abort(404)
    return add_status(rows[0])


def save_image(file):
    """Same rules as your student photo: JPEG/PNG, under 2 MB. Returns (filename, error)."""
    if not file or not file.filename:
        return None, None
    if not allowed_photo(file.filename):
        return None, "Event image must be a JPEG or PNG file."
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_PHOTO_SIZE:
        return None, "Event image must be under 2 MB."
    ext = file.filename.rsplit(".", 1)[1].lower()
    name = f"event-{datetime.now():%Y%m%d-%H%M%S}-{random.randint(100, 1000)}.{ext}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], name))
    return name, None


def remove_image(name):
    if name:
        path = os.path.join(app.config["UPLOAD_FOLDER"], name)
        if os.path.exists(path):
            os.remove(path)


def read_event_form(form, booked=0, editing=False):
    """Returns (values, errors)."""
    v = {k: form.get(k, "").strip() for k in (
        "title", "category", "event_date", "start_time", "venue",
        "capacity", "organizer_email", "reg_deadline", "description")}
    errors = []
    if not all(v.values()):
        errors.append("Please fill in all required fields.")
        return v, errors
    if v["category"] not in CATEGORIES:
        errors.append("Please choose a valid category.")
    if not EMAIL_RE.match(v["organizer_email"]):
        errors.append("Enter a valid organizer email.")
    try:
        cap = int(v["capacity"])
        if cap < 1:
            raise ValueError
        v["capacity"] = cap
        if cap < booked:
            errors.append(f"Seat capacity cannot be lower than the {booked} seats already booked.")
    except ValueError:
        errors.append("Seat capacity must be a whole number of at least 1.")
    try:
        ev_date = datetime.strptime(v["event_date"], "%Y-%m-%d").date()
        dl_date = datetime.strptime(v["reg_deadline"], "%Y-%m-%d").date()
        v["event_date"], v["reg_deadline"] = ev_date, dl_date
        if not editing and ev_date < date.today():
            errors.append("Event date cannot be in the past.")
        if dl_date > ev_date:
            errors.append("Registration deadline must be on or before the event date.")
    except ValueError:
        errors.append("Enter valid dates.")
    return v, errors


def db_error_text(err):
    print("MySQL error:", err)
    if err.errno in (1146, 1054):
        return "Event tables not found. Run events_schema.sql on your database first."
    return f"Database error: {err.msg}"


# ---------- routes ----------
@bp.route("/")
def list_events():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    upcoming = request.args.get("upcoming")
    where, params = [], []
    if q:
        where.append("(e.title LIKE %s OR e.venue LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if category in CATEGORIES:
        where.append("e.category = %s")
        params.append(category)
    if upcoming:
        where.append("e.event_date >= CURDATE()")
    sql = EVENT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " GROUP BY e.id ORDER BY e.event_date, e.start_time"
    try:
        events = [add_status(e) for e in fetch(sql, params)]
    except mysql.connector.Error as err:
        return db_error_text(err), 500
    return render_template("events/list.html", events=events, q=q, category=category,
                           upcoming=upcoming, categories=CATEGORIES,
                           message=MESSAGES.get(request.args.get("msg")))


@bp.route("/new", methods=["GET", "POST"])
def create():
    values, errors = {}, []
    if request.method == "POST":
        values, errors = read_event_form(request.form)
        image, img_err = save_image(request.files.get("image"))
        if img_err:
            errors.append(img_err)
        if not errors:
            conn = get_db()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO events (title, category, event_date, start_time, venue, capacity, "
                    "organizer_email, reg_deadline, description, image) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (values["title"], values["category"], values["event_date"], values["start_time"],
                     values["venue"], values["capacity"], values["organizer_email"],
                     values["reg_deadline"], values["description"], image))
                conn.commit()
                return redirect(url_for("events.list_events", msg="created"))
            except mysql.connector.Error as err:
                conn.rollback()
                remove_image(image)
                errors.append(db_error_text(err))
            finally:
                conn.close()
        else:
            remove_image(image)
    return render_template("events/form.html", editing=False, ev=values, errors=errors,
                           categories=CATEGORIES)


@bp.route("/<int:event_id>")
def details(event_id):
    ev = get_event(event_id)
    return render_template("events/details.html", ev=ev,
                           message=MESSAGES.get(request.args.get("msg")))


@bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
def edit(event_id):
    ev = get_event(event_id)
    errors = []
    if request.method == "POST":
        values, errors = read_event_form(request.form, booked=ev["booked"], editing=True)
        image, img_err = save_image(request.files.get("image"))
        if img_err:
            errors.append(img_err)
        if not errors:
            conn = get_db()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE events SET title=%s, category=%s, event_date=%s, start_time=%s, venue=%s, "
                    "capacity=%s, organizer_email=%s, reg_deadline=%s, description=%s, image=%s WHERE id=%s",
                    (values["title"], values["category"], values["event_date"], values["start_time"],
                     values["venue"], values["capacity"], values["organizer_email"],
                     values["reg_deadline"], values["description"], image or ev["image"], event_id))
                conn.commit()
                if image:
                    remove_image(ev["image"])
                return redirect(url_for("events.details", event_id=event_id, msg="updated"))
            except mysql.connector.Error as err:
                conn.rollback()
                remove_image(image)
                errors.append(db_error_text(err))
            finally:
                conn.close()
        else:
            remove_image(image)
        ev = {**ev, **values}          # keep what the person typed
    return render_template("events/form.html", editing=True, ev=ev, errors=errors,
                           categories=CATEGORIES)


@bp.route("/<int:event_id>/delete", methods=["POST"])
def delete(event_id):
    ev = get_event(event_id)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE id = %s", (event_id,))  # registrations cascade
        conn.commit()
    finally:
        conn.close()
    remove_image(ev["image"])
    return redirect(url_for("events.list_events", msg="deleted"))


@bp.route("/<int:event_id>/register", methods=["GET", "POST"])
def register(event_id):
    ev = get_event(event_id)
    errors, values = [], {}
    if request.method == "POST":
        values = {k: request.form.get(k, "").strip() for k in ("full_name", "email", "mobile", "seats")}
        values["email"] = values["email"].lower()
        if not all(values.values()):
            errors.append("Please fill in all required fields.")
        else:
            if not EMAIL_RE.match(values["email"]):
                errors.append("Enter a valid email address.")
            if not re.fullmatch(r"\d{10}", values["mobile"]):
                errors.append("Mobile number must be exactly 10 digits.")
            if values["seats"] not in ("1", "2"):
                errors.append("You can reserve 1 or 2 seats.")
        if not errors and ev["is_closed"]:
            errors.append("Registration for this event is closed.")
        if not errors:
            seats = int(values["seats"])
            conn = get_db()
            try:
                cur = conn.cursor()
                conn.start_transaction()
                # lock the event row so two people can't take the last seat together
                cur.execute("SELECT capacity FROM events WHERE id = %s FOR UPDATE", (event_id,))
                capacity = cur.fetchone()[0]
                cur.execute("SELECT COALESCE(SUM(seats),0) FROM event_registrations WHERE event_id = %s",
                            (event_id,))
                left = capacity - int(cur.fetchone()[0])
                if left <= 0:
                    errors.append("Sorry, this event is full.")
                elif seats > left:
                    errors.append(f"Only {left} seat(s) left.")
                else:
                    cur.execute(
                        "INSERT INTO event_registrations (event_id, full_name, email, mobile, seats) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (event_id, values["full_name"], values["email"], values["mobile"], seats))
                    conn.commit()
                    return redirect(url_for("events.details", event_id=event_id, msg="registered"))
                conn.rollback()
            except mysql.connector.Error as err:
                conn.rollback()
                errors.append("This email is already registered for this event."
                              if err.errno == 1062 else db_error_text(err))
            finally:
                conn.close()
    return render_template("events/register.html", ev=ev, errors=errors, v=values)
