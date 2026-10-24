"""Community Event Manager - a very simple Flask demo.

No database and no JavaScript: events live in a plain Python list,
so all data resets when the server restarts.
All form validation is done here in Python (not in the HTML).
"""
import re
from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash, abort

app = Flask(__name__)
app.secret_key = "demo-key"

CATEGORIES = ["Workshop", "Community", "Career"]
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# ---------------------------------------------------------------- dummy data
events = [
    {
        "id": 1,
        "title": "Digital Skills Saturday",
        "category": "Workshop",
        "event_date": date(2026, 10, 5),
        "start_time": datetime.strptime("10:00", "%H:%M").time(),
        "venue": "MITRAz Training Centre",
        "seat_capacity": 30,
        "booked_seats": 12,
        "organizer_email": "organizer@example.com",
        "registration_deadline": date(2026, 10, 4),
        "description": "A practical introduction to everyday digital skills for local learners.",
    }
]
registrations = []   # each item: {"event_id": 1, "email": "a@b.com"}
next_id = 2          # id given to the next new event


# ------------------------------------------------------------------- helpers
def update_seats(event):
    """Recalculate available seats and the progress-bar percentage."""
    event["available_seats"] = event["seat_capacity"] - event["booked_seats"]
    event["percentage"] = round(event["booked_seats"] / event["seat_capacity"] * 100)


def get_event(event_id):
    """Return the event with this id, or show a 404 page."""
    for event in events:
        if event["id"] == event_id:
            return event
    abort(404)


def parse_date(text):
    """Turn 'YYYY-MM-DD' into a date, or return None if it is invalid."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_time(text):
    """Turn 'HH:MM' into a time, or return None if it is invalid."""
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None


def event_to_form(event):
    """Convert an event into plain text values to fill the edit form."""
    return {
        "title": event["title"],
        "category": event["category"],
        "event_date": event["event_date"].strftime("%Y-%m-%d"),
        "start_time": event["start_time"].strftime("%H:%M"),
        "venue": event["venue"],
        "seat_capacity": str(event["seat_capacity"]),
        "organizer_email": event["organizer_email"],
        "registration_deadline": event["registration_deadline"].strftime("%Y-%m-%d"),
        "description": event["description"],
    }


def validate_event(form, booked_seats=0):
    """Check the event form. Returns (errors, cleaned_data)."""
    errors = []
    title = form.get("title", "").strip()
    category = form.get("category", "")
    venue = form.get("venue", "").strip()
    email = form.get("organizer_email", "").strip()
    description = form.get("description", "").strip()
    event_date = parse_date(form.get("event_date", ""))
    start_time = parse_time(form.get("start_time", ""))
    deadline = parse_date(form.get("registration_deadline", ""))
    capacity_text = form.get("seat_capacity", "").strip()

    if not title:
        errors.append("Event title is required.")
    if category not in CATEGORIES:
        errors.append("Please choose a valid category.")
    if event_date is None:
        errors.append("Please enter a valid event date.")
    if start_time is None:
        errors.append("Please enter a valid start time.")
    if not venue:
        errors.append("Venue is required.")

    if not capacity_text.isdigit() or int(capacity_text) < 1:
        errors.append("Seat capacity must be a whole number of 1 or more.")
        capacity = 0
    else:
        capacity = int(capacity_text)
        if capacity < booked_seats:
            errors.append(f"Seat capacity cannot be lower than the {booked_seats} seats already booked.")

    if not EMAIL_PATTERN.match(email):
        errors.append("Please enter a valid organizer email (e.g. name@example.com).")
    if deadline is None:
        errors.append("Please enter a valid registration deadline.")
    elif event_date and deadline > event_date:
        errors.append("Registration deadline cannot be after the event date.")
    if not description:
        errors.append("Description is required.")

    data = {
        "title": title, "category": category, "event_date": event_date,
        "start_time": start_time, "venue": venue, "seat_capacity": capacity,
        "organizer_email": email, "registration_deadline": deadline,
        "description": description,
    }
    return errors, data


def validate_registration(form, event):
    """Check the registration form. Returns (errors, cleaned_data)."""
    errors = []
    name = form.get("full_name", "").strip()
    email = form.get("email", "").strip().lower()
    mobile = form.get("mobile", "").strip()
    seats_text = form.get("seats_requested", "")

    if not name:
        errors.append("Full name is required.")
    if not EMAIL_PATTERN.match(email):
        errors.append("Please enter a valid email address (e.g. you@example.com).")
    if not (mobile.isdigit() and len(mobile) == 10):
        errors.append("Mobile number must be exactly 10 digits.")
    if seats_text not in ("1", "2"):
        errors.append("You can request 1 or 2 seats only.")
        seats = 0
    else:
        seats = int(seats_text)

    if date.today() > event["registration_deadline"]:
        errors.append("Registration for this event has closed.")
    if seats and seats > event["available_seats"]:
        errors.append(f"Only {event['available_seats']} seat(s) are available.")
    if any(r["event_id"] == event["id"] and r["email"] == email for r in registrations):
        errors.append("This email has already registered for this event.")

    return errors, {"email": email, "seats": seats}


def show_errors(errors):
    """Show each error message at the top of the page."""
    for message in errors:
        flash(message, "error")


# -------------------------------------------------------------------- routes
@app.route("/")
def home():
    """List all events, sorted by date."""
    ordered = sorted(events, key=lambda e: (e["event_date"], e["start_time"]))
    return render_template("home.html", events=ordered)


@app.route("/events/<int:event_id>")
def event_details(event_id):
    """Show one event."""
    return render_template("details.html", event=get_event(event_id))


@app.route("/events/new", methods=["GET", "POST"])
def create_event():
    """Show the new-event form and save the event when valid."""
    global next_id
    form = {}
    if request.method == "POST":
        form = request.form
        errors, data = validate_event(form)
        if not errors:
            data.update(id=next_id, booked_seats=0)
            update_seats(data)
            events.append(data)
            next_id += 1
            flash("Event published successfully!")
            return redirect(url_for("home"))
        show_errors(errors)
    return render_template("event_form.html", editing=False, event=None,
                           form=form, categories=CATEGORIES)


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def edit_event(event_id):
    """Show the edit form and update the event when valid."""
    event = get_event(event_id)
    form = event_to_form(event)
    if request.method == "POST":
        form = request.form
        errors, data = validate_event(form, booked_seats=event["booked_seats"])
        if not errors:
            event.update(data)
            update_seats(event)
            flash("Event updated successfully!")
            return redirect(url_for("event_details", event_id=event_id))
        show_errors(errors)
    return render_template("event_form.html", editing=True, event=event,
                           form=form, categories=CATEGORIES)


@app.route("/events/<int:event_id>/register", methods=["GET", "POST"])
def register_event(event_id):
    """Show the registration form and reserve seats when valid."""
    event = get_event(event_id)
    form = {"seats_requested": "1"}
    if request.method == "POST":
        form = request.form
        errors, data = validate_registration(form, event)
        if not errors:
            event["booked_seats"] += data["seats"]
            update_seats(event)
            registrations.append({"event_id": event_id, "email": data["email"]})
            flash(f"Registered {data['seats']} seat(s) successfully!")
            return redirect(url_for("event_details", event_id=event_id))
        show_errors(errors)
    return render_template("register.html", event=event, form=form)


@app.route("/events/<int:event_id>/delete", methods=["POST"])
def delete_event(event_id):
    """Remove an event and its registrations."""
    event = get_event(event_id)
    events.remove(event)
    registrations[:] = [r for r in registrations if r["event_id"] != event_id]
    flash(f"Event '{event['title']}' deleted.")
    return redirect(url_for("home"))


# Fill in seat numbers for the dummy data
for item in events:
    update_seats(item)

if __name__ == "__main__":
    app.run(debug=True)
