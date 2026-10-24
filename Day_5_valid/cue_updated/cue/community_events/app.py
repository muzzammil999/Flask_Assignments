"""Community Event Manager - a very simple Flask project.

How this project works
----------------------
1. There is NO database. All events are stored in a normal Python list
   called ``events``. Every event is a dictionary inside that list.
2. Because the data lives in memory, everything resets when the server
   restarts.
3. All form checking (validation) is done here in Python, not in HTML.
4. The search/filter panel on the home page is only for display.
Pages (routes)
----------------------------------------------------------------
    /                           -> home page (list of events)
    /events/new                 -> create a new event
    /events/<id>                -> event details
    /events/<id>/edit           -> edit an event
    /events/<id>/register       -> register seats for an event
    /events/<id>/delete         -> delete an event (POST only)
"""        

import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, abort

# Create the Flask application object.
app = Flask(__name__)

# flash() messages need a secret key to work (it is used by the session).
app.secret_key = "demo-key"

# ------------------------------------------------------------------
# Settings (constants)
# ------------------------------------------------------------------
# Folder where uploaded event images are saved: static/uploads

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")

# Maximum image size allowed: 2 MB written in bytes (2 * 1024 * 1024).
MAX_IMAGE_SIZE = 2 * 1024 * 1024

# The only categories a user can choose from.
CATEGORIES = ["Workshop", "Community", "Career"]

# Image file types we accept.
ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg"]

# ------------------------------------------------------------------
# Data (in-memory lists)
# ------------------------------------------------------------------
# List that stores all event dictionaries. One sample event is added
# so the home page is not empty when the server starts.
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
        "image_filename": None,
    }
]

# List that stores every registration, so one email cannot register
# twice for the same event. Each item looks like:
# {"event_id": 1, "email": "a@b.com"}
registrations = []


# ==================================================================
# Helper functions
# ==================================================================

def update_seats(event):
    """Calculate the available seats and the progress-bar percentage.

    Explanation:
        The templates show "available seats" and a progress bar, but
        these two values are not typed by the user. They are worked out
        from the capacity and the booked seats, so we call this function
        every time those numbers change.

    Parameters:
        event (dict): the event dictionary that will be updated.

    Returns:
        Nothing. It adds/updates two keys inside the same dictionary:
        "available_seats" and "percentage".
    """
    # available seats = total seats - seats already booked
    event["available_seats"] = event["seat_capacity"] - event["booked_seats"]

    # percentage of seats that are booked (used for the progress bar)
    event["percentage"] = round(event["booked_seats"] / event["seat_capacity"] * 100)


def get_event(event_id):
    """Find one event in the list using its id.

    Explanation:
        Many routes (details, edit, register, delete) need one event.
        This function loops through the events list and returns the
        event whose id matches. If nothing matches, the user is shown
        a 404 "Not Found" page.

    Parameters:
        event_id (int): the id of the event we are looking for.

    Returns:
        dict: the matching event dictionary.
    """
    for event in events:
        # Compare each event's id with the id we want.
        if event["id"] == event_id:
            return event

    # Loop finished without a match -> show the 404 error page.
    abort(404)


def get_next_id():
    """Give the id number for a new event.

    Explanation:
        We find the biggest id that is already used and add 1 to it.
        (Using len(events) + 1 is not safe, because after deleting an
        event two events could end up with the same id.)

    Returns:
        int: a new unused id.
    """
    biggest = 0
    for event in events:
        if event["id"] > biggest:
            biggest = event["id"]
    return biggest + 1


def parse_date(text):
    """Convert text like '2026-10-05' into a date object.

    Explanation:
        Form values always arrive as text. We need a real date so we
        can compare dates and print them nicely in the templates.

    Parameters:
        text (str): the date text from the form (format YYYY-MM-DD).

    Returns:
        date: the date object, or None if the text is not a valid date.
    """
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        # strptime raises ValueError when the text does not match.
        return None


def parse_time(text):
    """Convert text like '10:30' into a time object.

    Explanation:
        Works exactly like parse_date, but for the start time.

    Parameters:
        text (str): the time text from the form (format HH:MM).

    Returns:
        time: the time object, or None if the text is not a valid time.
    """
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None


def is_valid_email(email):
    """Check if an email looks correct.

    Explanation:
        This is a simple check, not a perfect one. A valid email must:
        - contain exactly one "@"
        - have some text before the "@"
        - have a "." in the part after the "@" (not at the very start
          or end of that part)
        - contain no spaces

    Parameters:
        email (str): the email text to check.

    Returns:
        bool: True if the email looks valid, otherwise False.
    """
    if " " in email:
        return False
    if email.count("@") != 1:
        return False

    # Split "name@site.com" into "name" and "site.com".
    name, domain = email.split("@")
    if name == "":
        return False
    if "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith("."):
        return False
    return True


def event_to_form(event):
    """Turn an event into plain text so the edit form can show it.

    Explanation:
        Inside the event, the date and time are date/time objects, but
        an HTML input needs plain text like "2026-10-05". This function
        builds a dictionary of text values to pre-fill the edit form.

    Parameters:
        event (dict): the event we want to edit.

    Returns:
        dict: form values as text, using the same names as the HTML
        input fields.
    """
    form = {
        "title": event["title"],
        "category": event["category"],
        # strftime() converts a date/time object back into text.
        "event_date": event["event_date"].strftime("%Y-%m-%d"),
        "start_time": event["start_time"].strftime("%H:%M"),
        "venue": event["venue"],
        "seat_capacity": str(event["seat_capacity"]),
        "organizer_email": event["organizer_email"],
        "registration_deadline": event["registration_deadline"].strftime("%Y-%m-%d"),
        "description": event["description"],
    }
    return form


def show_errors(errors):
    """Show every error message at the top of the page.

    Explanation:
        flash() stores a message that base.html shows on the next page
        load. We use the category "error" so the message gets the red
        error style.

    Parameters:
        errors (list): list of error message strings.
    """
    for message in errors:
        flash(message, "error")


@app.context_processor
def menu_links():
    """Give the menu links to EVERY template automatically.

    Explanation:
        base.html has two menu links ("Event details" and
        "Registration") that need an event id. Instead of passing these
        links from every route, this function runs before each template
        is drawn and sends them to all templates.
        The links point to the first event. If there are no events, they
        point to the home page.

    Returns:
        dict: the variables "nav_details" and "nav_register".
    """
    if len(events) > 0:
        first_id = events[0]["id"]
        links = {
            "nav_details": url_for("event_details", event_id=first_id),
            "nav_register": url_for("register_event", event_id=first_id),
        }
    else:
        links = {
            "nav_details": url_for("home"),
            "nav_register": url_for("home"),
        }
    return links


# ==================================================================
# Image functions
# ==================================================================

def get_extension(filename):
    """Get the file type of a file name in lowercase.

    Example:
        "Photo.JPG" -> "jpg"

    Parameters:
        filename (str): the original name of the uploaded file.

    Returns:
        str: the extension without the dot (empty text if none).
    """
    if "." not in filename:
        return ""
    # rsplit(".", 1) splits only at the LAST dot, so "a.b.png" -> "png".
    return filename.rsplit(".", 1)[1].lower()


def check_image(image):
    """Validate the uploaded image (optional field).

    Explanation:
        The image is optional, so no file means no error. If a file was
        chosen we check two rules:
        1. it must be a PNG or JPG/JPEG file
        2. it must be 2 MB or smaller

    Parameters:
        image: the uploaded file object from request.files (or None).

    Returns:
        list: error messages. An empty list means the image is fine.
    """
    errors = []

    # No file chosen -> nothing to check.
    if image is None or image.filename == "":
        return errors

    # Rule 1: file type.
    if get_extension(image.filename) not in ALLOWED_EXTENSIONS:
        errors.append("Image must be a PNG or JPEG file.")
        return errors

    # Rule 2: file size. read() gives the file content as bytes, so
    # len() is the size in bytes.
    data = image.read()
    image.seek(0)   # move back to the start so the file can be saved later
    if len(data) > MAX_IMAGE_SIZE:
        errors.append("Image must be 2 MB or smaller.")

    return errors


def save_image(image, event_id):
    """Save the uploaded image inside static/uploads.

    Explanation:
        The file is saved with a simple name based on the event id,
        for example "event_3.jpg". The name is returned so we can store
        it in the event dictionary and show the image later.

    Parameters:
        image: the uploaded file object (or None).
        event_id (int): id of the event that owns this image.

    Returns:
        str: the saved file name, or None if no image was uploaded.
    """
    # No file chosen -> nothing to save.
    if image is None or image.filename == "":
        return None

    filename = "event_" + str(event_id) + "." + get_extension(image.filename)

    # Make sure the upload folder exists (does nothing if it already does).
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Save the file on disk.
    image.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


# ==================================================================
# Validation functions
# ==================================================================

def validate_event(form, booked_seats=0):
    """Check the create/edit event form.

    Explanation:
        Every field is read from the form, cleaned (extra spaces are
        removed) and checked. For each problem, a message is added to
        the errors list. If the list stays empty, the form is valid.

    Parameters:
        form: the submitted form values (request.form).
        booked_seats (int): seats already booked. It is 0 for a new
            event. When editing, the new capacity cannot be lower than
            this number.

    Returns:
        tuple: (errors, data)
            errors - list of error messages (empty if all is fine)
            data   - dictionary of cleaned values, ready to save
    """
    errors = []

    # Read the text fields. strip() removes spaces at the start and end.
    title = form.get("title", "").strip()
    category = form.get("category", "")
    venue = form.get("venue", "").strip()
    email = form.get("organizer_email", "").strip()
    description = form.get("description", "").strip()
    capacity_text = form.get("seat_capacity", "").strip()

    # Convert the text of dates/time into real date/time objects.
    # They become None if the text is invalid.
    event_date = parse_date(form.get("event_date", ""))
    start_time = parse_time(form.get("start_time", ""))
    deadline = parse_date(form.get("registration_deadline", ""))

    # --- Check each field ---
    if title == "":
        errors.append("Event title is required.")

    if category not in CATEGORIES:
        errors.append("Please choose a valid category.")

    if event_date is None:
        errors.append("Please enter a valid event date.")

    if start_time is None:
        errors.append("Please enter a valid start time.")

    if venue == "":
        errors.append("Venue is required.")

    # Capacity must be a whole number that is 1 or more.
    capacity = 0
    if capacity_text.isdigit() and int(capacity_text) >= 1:
        capacity = int(capacity_text)
        # Do not allow fewer seats than the seats already booked.
        if capacity < booked_seats:
            errors.append("Seat capacity cannot be lower than the "
                          + str(booked_seats) + " seats already booked.")
    else:
        errors.append("Seat capacity must be a whole number of 1 or more.")

    if not is_valid_email(email):
        errors.append("Please enter a valid organizer email (e.g. name@example.com).")

    # The deadline must be valid and cannot be after the event date.
    if deadline is None:
        errors.append("Please enter a valid registration deadline.")
    elif event_date is not None and deadline > event_date:
        errors.append("Registration deadline cannot be after the event date.")

    if description == "":
        errors.append("Description is required.")

    # Put all the cleaned values in one dictionary.
    data = {
        "title": title,
        "category": category,
        "event_date": event_date,
        "start_time": start_time,
        "venue": venue,
        "seat_capacity": capacity,
        "organizer_email": email,
        "registration_deadline": deadline,
        "description": description,
    }
    return errors, data


def validate_registration(form, event):
    """Check the registration form for an event.

    Explanation:
        Checks the person's name, email, mobile number and number of
        seats. Then checks the event rules: the deadline has not passed,
        enough seats are free, and the same email has not registered
        before for this event.

    Parameters:
        form: the submitted form values (request.form).
        event (dict): the event the person wants to join.

    Returns:
        tuple: (errors, data)
            errors - list of error messages (empty if all is fine)
            data   - dictionary with the cleaned "email" and "seats"
    """
    errors = []

    # Read and clean the form values.
    name = form.get("full_name", "").strip()
    email = form.get("email", "").strip().lower()   # lower() so A@x.com == a@x.com
    mobile = form.get("mobile", "").strip()
    seats_text = form.get("seats_requested", "")

    if name == "":
        errors.append("Full name is required.")

    if not is_valid_email(email):
        errors.append("Please enter a valid email address (e.g. you@example.com).")

    # Mobile must be digits only and exactly 10 characters long.
    if not (mobile.isdigit() and len(mobile) == 10):
        errors.append("Mobile number must be exactly 10 digits.")

    # Only 1 or 2 seats are allowed per registration.
    seats = 0
    if seats_text == "1" or seats_text == "2":
        seats = int(seats_text)
    else:
        errors.append("You can request 1 or 2 seats only.")

    # Registration closes after the deadline date.
    if date.today() > event["registration_deadline"]:
        errors.append("Registration for this event has closed.")

    # Make sure enough seats are free.
    if seats > event["available_seats"]:
        errors.append("Only " + str(event["available_seats"]) + " seat(s) are available.")

    # Check the registrations list for the same email on the same event.
    for item in registrations:
        if item["event_id"] == event["id"] and item["email"] == email:
            errors.append("This email has already registered for this event.")

    data = {"email": email, "seats": seats}
    return errors, data


# ==================================================================
# Routes
# ==================================================================

@app.route("/")
def home():
    """Home page: show all events, sorted by date and time.

    Explanation:
        sorted() makes a new ordered list, so the original ``events``
        list is not changed. Each event is sorted by its date first and
        then by its start time.

    Returns:
        The rendered index.html page.
    """
    # key=... tells sorted() what to compare. Here: (date, time).
    ordered = sorted(events, key=lambda e: (e["event_date"], e["start_time"]))
    return render_template("index.html", events=ordered, page="home")


@app.route("/events/<int:event_id>")
def event_details(event_id):
    """Details page: show one event.

    Parameters:
        event_id (int): taken from the URL, e.g. /events/2.

    Returns:
        The rendered details.html page (or 404 if the event is missing).
    """
    event = get_event(event_id)
    return render_template("details.html", event=event, page="details")


@app.route("/events/new", methods=["GET", "POST"])
def create_event():
    """Create page: show the new-event form and save the event.

    Explanation:
        GET  -> show an empty form.
        POST -> the form was submitted:
                1. validate the fields and the image
                2. if there are errors, show them and show the form again
                   (the typed values are kept)
                3. if all is fine, save the event in the list and go to
                   the home page

    Returns:
        The create.html page, or a redirect to the home page.
    """
    form = {}   # empty form values for the first visit (GET)

    if request.method == "POST":
        form = request.form
        errors, data = validate_event(form)

        # The image comes from request.files (not request.form).
        image = request.files.get("image")
        errors = errors + check_image(image)

        if len(errors) == 0:
            # Add the extra values a new event needs.
            new_id = get_next_id()
            data["id"] = new_id
            data["booked_seats"] = 0               # nobody has booked yet
            data["image_filename"] = save_image(image, new_id)
            update_seats(data)

            # Add the new event to the list.
            events.append(data)
            flash("Event published successfully. Your new event now appears in the list.")
            return redirect(url_for("home"))

        # There were errors -> show them (page is shown again below).
        show_errors(errors)

    return render_template("create.html", form=form, categories=CATEGORIES, page="create")


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def edit_event(event_id):
    """Edit page: show the event form and update the event.

    Explanation:
        GET  -> show the form filled with the current event values.
        POST -> validate the new values. The capacity cannot be lower
                than the seats already booked. If the image field is
                empty, the old image is kept.

    Parameters:
        event_id (int): id of the event to edit (from the URL).

    Returns:
        The edit.html page, or a redirect to the event details page.
    """
    event = get_event(event_id)

    # First visit (GET): fill the form with the current event values.
    form = event_to_form(event)

    if request.method == "POST":
        form = request.form
        errors, data = validate_event(form, event["booked_seats"])

        image = request.files.get("image")
        errors = errors + check_image(image)

        if len(errors) == 0:
            # Save a new image only if the user chose one.
            new_image = save_image(image, event_id)
            if new_image is not None:
                data["image_filename"] = new_image

            # Copy every new value into the existing event dictionary.
            event.update(data)
            update_seats(event)
            flash("Event updated successfully!")
            return redirect(url_for("event_details", event_id=event_id))

        show_errors(errors)

    return render_template("edit.html", event=event, form=form,
                           categories=CATEGORIES, page="edit")


@app.route("/events/<int:event_id>/register", methods=["GET", "POST"])
def register_event(event_id):
    """Register page: reserve seats for an event.

    Explanation:
        GET  -> show the registration form (1 seat selected).
        POST -> validate the form. If it is valid, the seats are added
                to booked_seats and the registration is remembered in
                the registrations list.

    Parameters:
        event_id (int): id of the event to join (from the URL).

    Returns:
        The register.html page, or a redirect to the event details page.
    """
    event = get_event(event_id)
    form = {"seats_requested": "1"}   # default choice on the first visit

    if request.method == "POST":
        form = request.form
        errors, data = validate_registration(form, event)

        if len(errors) == 0:
            # Add the requested seats to the booked seats.
            event["booked_seats"] = event["booked_seats"] + data["seats"]
            update_seats(event)

            # Remember this email so it cannot register again.
            registrations.append({"event_id": event_id, "email": data["email"]})

            flash("Registered " + str(data["seats"]) + " seat(s) successfully!")
            return redirect(url_for("event_details", event_id=event_id))

        show_errors(errors)

    return render_template("register.html", event=event, form=form, page="register")


@app.route("/events/<int:event_id>/delete", methods=["POST"])
def delete_event(event_id):
    """Delete an event and all its registrations.

    Explanation:
        Only POST is allowed (no GET), so an event can never be deleted
        just by opening a link. The delete button on the home page is a
        small form that sends a POST request.

    Parameters:
        event_id (int): id of the event to delete (from the URL).

    Returns:
        A redirect to the home page.
    """
    event = get_event(event_id)

    # Remove the event from the events list.
    events.remove(event)

    # Build a new registrations list that keeps only the registrations
    # of the OTHER events.
    remaining = []
    for item in registrations:
        if item["event_id"] != event_id:
            remaining.append(item)
    registrations.clear()          # empty the original list
    registrations.extend(remaining)  # put the kept items back

    flash("Event '" + event["title"] + "' deleted.")
    return redirect(url_for("home"))


# ------------------------------------------------------------------
# Start-up
# ------------------------------------------------------------------
# The sample event needs its available_seats and percentage values.
for item in events:
    update_seats(item)

# Run the development server only when this file is started directly
# with "python app.py".
if __name__ == "__main__":
    app.run(debug=True)
