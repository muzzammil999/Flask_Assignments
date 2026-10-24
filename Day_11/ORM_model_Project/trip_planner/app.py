"""
app.py - THE ENTRY POINT: routes, request handling, and glue
============================================================

WHAT THIS FILE DOES
    Creates the Flask app, wires it to the settings (config.py) and the data
    layer (models.py), and defines the ROUTES: the functions that run when a
    browser asks for a URL. Each route is deliberately short:

        1. read what the user sent (request)
        2. ask models.py to validate / fetch / save data
        3. send back a page (render_template) or redirect somewhere

    No SQL and no validation rules live here - those belong to models.py.

HOW TO RUN
        pip install -r requirements.txt
        python app.py            ->  open http://127.0.0.1:5000

--------------------------------------------------------------------------
KEY TERMS USED IN THIS FILE
--------------------------------------------------------------------------
Flask
    A small Python "web framework": a toolkit that listens for browser requests
    and lets you answer them with Python functions.

Route / Routing
    A mapping from a URL to a function. `@app.route("/trips")` means "when the
    browser asks for /trips, run the function right below".
    Analogy: the receptionist's directory - "Accounting? Room 12."

Request / Response
    The request is the browser's question (URL + any form data); the response
    is your answer (usually an HTML page, or a redirect).

HTTP methods: GET and POST
    GET = "show me a page" (opening a link). POST = "here is data, please act
    on it" (submitting a form). One URL can handle both, e.g. a form page.

Template (Jinja)
    An HTML file with blanks like {{ trip.destination }} that Flask fills in.
    Analogy: a mail-merge letter.

Redirect
    Telling the browser "go to this other URL now". After a successful form
    POST we redirect, so pressing Refresh cannot submit the form twice.

Session
    A small, signed cookie that remembers who you are between requests, because
    HTTP itself has no memory. After login we store session["user_id"].
    Analogy: a wristband at a festival - show it at every door.

Flash message
    A one-time message ("Trip created.") shown on the NEXT page, then forgotten.

CSRF (Cross-Site Request Forgery)
    An attack where another website tricks your browser into submitting a form
    to this site using your login. Defence: every form carries a secret token
    that only our own pages know.

Decorator
    The `@something` line above a function; it wraps the function with extra
    behaviour. `@login_required` adds "must be logged in" to a route.

Application context
    Flask's "we are inside the app" state; database calls need it. Inside a
    request it exists automatically; outside (like start-up) we create it with
    `with app.app_context():`.
"""

import os
import secrets
from functools import wraps

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
from sqlalchemy.exc import IntegrityError

from config import Config
from models import (Activity, Trip, User, db, image_belongs_to_user)

# =============================================================================
# 1. CREATE THE APP AND CONNECT THE PIECES
# =============================================================================
app = Flask(__name__)
app.config.from_object(Config)      # load every setting from config.py
db.init_app(app)                    # connect the `db` object (models.py) to this app

# On start-up: make sure the photo folder exists and create any missing tables.
# create_all() builds tables from the model classes; existing tables and their
# data are left untouched.
with app.app_context():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()


# =============================================================================
# 2. SECURITY HELPERS: CSRF TOKEN + LOGIN GUARD
# =============================================================================
def csrf_token():
    """Return this visitor's secret form token (creating it the first time).
    Every <form method="post"> in the templates includes it as a hidden field."""
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.context_processor
def inject_template_values():
    """Make `csrf_token()` and `categories` available in EVERY template
    without passing them from each route."""
    return {"csrf_token": csrf_token, "categories": Config.CATEGORIES}


@app.before_request
def check_csrf():
    """Runs before EVERY request. For POSTs, the token in the form must equal the
    one in the session; otherwise we refuse with HTTP 400 (see error handlers)."""
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        # compare_digest compares in constant time (safer for secrets).
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400)


def login_required(view):
    """Decorator: visitors who are not logged in are sent to the login page.
    Login state = whether session["user_id"] exists (set in login())."""
    @wraps(view)                       # keeps the wrapped function's name for Flask 
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)   # logged in -> run the real route
    return wrapped


# =============================================================================
# 3. PHOTO HELPERS
# =============================================================================
# Every create/edit route that has a photo follows the same 4 steps:
#   read_image_upload()  validate the uploaded file (nothing written to disk yet)
#   pick_image_name()    save the new file / decide which filename to store
#   record.save()        store the filename in the database (inside save_with_image)
#   remove_image_file()  delete the OLD file now that it is unused
def read_image_upload(errors):
    """Validate the optional "image" upload.

    Returns (bytes, extension), or (None, None) if nothing valid was uploaded.
    On a problem it adds errors["image"] so the form can show it.
    """
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return None, None
    data = upload.read(Config.MAX_IMAGE_BYTES + 1)   # +1 lets us detect "too big"
    if len(data) > Config.MAX_IMAGE_BYTES:
        errors["image"] = "Image must be 5 MB or smaller."
        return None, None
    ext = sniff_image_type(data)
    if ext is None:
        errors["image"] = "Upload a PNG, JPG, GIF or WEBP image."
        return None, None
    return data, ext


def sniff_image_type(data):
    """Identify the REAL image type from the file's first bytes ("magic numbers").
    The filename the user gave is never trusted, because it can lie."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def pick_image_name(existing_name, data, ext):
    """Decide which photo filename the record should have after this form.

    new upload        -> save it under a random name and return that name
    "remove" ticked   -> None (no photo)
    otherwise         -> keep `existing_name`
    Random names stop files overwriting each other and stop path tricks.
    """
    if data is not None:
        name = f"{secrets.token_hex(16)}.{ext}"
        with open(os.path.join(Config.UPLOAD_FOLDER, name), "wb") as f:
            f.write(data)
        return name
    if request.form.get("remove_image") == "1":
        return None
    return existing_name


def remove_image_file(name):
    """Delete a photo file from disk; silently ignores None or missing files."""
    if name:
        try:
            os.remove(os.path.join(Config.UPLOAD_FOLDER, os.path.basename(name)))
        except OSError:
            pass


def save_with_image(record, new_name, old_name):
    """Save `record` to the database, then tidy the photo files.

    If the save fails, the brand-new file is deleted again (no orphan files).
    If it succeeds and the photo changed, the old file is deleted.
    """
    try:
        record.save()
    except Exception:
        if new_name and new_name != old_name:
            remove_image_file(new_name)
        raise
    if old_name and old_name != new_name:
        remove_image_file(old_name)


# =============================================================================
# 4. ROUTES - ACCOUNTS (register, login, logout)
# =============================================================================
@app.route("/")
def home():
    """Landing page. GET /  ->  index.html

    Logged-in users also see up to 6 of their completed trips as samples.
    """
    trips = []
    if "user_id" in session:
        trips = Trip.completed_for(session["user_id"], limit=6)
    return render_template("index.html", trips=trips)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Sign-up. GET shows the form; POST creates the account. -> register.html"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", ""
                                    )
        confirm = request.form.get("confirm_password", "")

        errors = User.validate_registration(username, password, confirm)   # models.py
        if not errors:
            try:
                User.register(username, password)                          # models.py -> DB
            except IntegrityError:
                # Two people picked the same name at the same instant; the
                # database's UNIQUE rule caught it.
                errors["username"] = "That username is already registered."
        if errors:
            return render_template("register.html", errors=errors, username=username)

        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", errors={}, username="")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Sign-in. GET shows the form; POST checks the password. -> login.html"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.find_by_username(username)                             # models.py -> DB
        if user and user.check_password(password):
            session.clear()                       # start a fresh session (prevents "session fixation")
            session["user_id"] = user.id          # <- this is what "logged in" means
            session["username"] = user.username
            flash("You are logged in.", "success")
            return redirect(url_for("my_trips"))
        # Same message for "no such user" and "wrong password" so attackers
        # cannot discover which usernames exist.
        return render_template("login.html", error="Invalid username or password.", username=username)
    return render_template("login.html", error=None, username="")


@app.route("/logout", methods=["POST"])
def logout():
    """Sign-out. POST-only (with CSRF) so another site can't log you out."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# =============================================================================
# 5. ROUTES - TRIPS
# =============================================================================
@app.route("/trips")
@login_required
def my_trips():
    """List the user's upcoming/ongoing trips. -> my_trips.html"""
    user_id = session["user_id"]
    return render_template(
        "my_trips.html",
        trips=Trip.active_for(user_id),
        completed_count=Trip.count_completed(user_id),
    )


@app.route("/trips/new", methods=["GET", "POST"])
@login_required
def create_trip():
    """Create a trip. GET shows the empty form; POST saves. -> trip_form.html"""
    if request.method == "POST":
        values, errors = Trip.validate(request.form)           # 1. check the input
        data, ext = read_image_upload(errors)                  #    check the photo
        if errors:                                             # 2. problems? show form again
            return render_template("trip_form.html", trip=None, errors=errors,
                                   values=request.form, page_title="Create Trip")

        image_name = pick_image_name(None, data, ext)          # 3. store photo
        trip = Trip(owner_id=session["user_id"], image_filename=image_name, **values)
        save_with_image(trip, image_name, None)                # 4. INSERT into the database

        flash("Trip created. Add your activities next.", "success")
        return redirect(url_for("my_trips"))
    return render_template("trip_form.html", trip=None, errors={}, values={},
                           page_title="Create Trip")


@app.route("/trips/<int:trip_id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(trip_id):
    """Edit a trip. <int:trip_id> in the URL is passed in as the argument.
    -> trip_form.html"""
    trip = Trip.get_owned(trip_id, session["user_id"])         # None if not yours
    if not trip:
        flash("Trip not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))

    if request.method == "POST":
        values, errors = Trip.validate(request.form)
        if not errors:
            # Refuse dates that would strand an existing activity outside the trip.
            stranded = trip.first_activity_outside(values["start_date"], values["end_date"])
            if stranded:
                errors["date_range"] = (
                    f'Cannot change dates: activity "{stranded.name}" on '
                    f"{stranded.activity_date} would fall outside the new trip dates. "
                    "Update or remove that activity first.")
        data, ext = read_image_upload(errors)
        if errors:
            return render_template("trip_form.html", trip=trip, errors=errors,
                                   values=request.form, page_title="Edit Trip")

        old_name = trip.image_filename
        image_name = pick_image_name(old_name, data, ext)
        trip.apply(values)                                     # change the object's fields...
        trip.image_filename = image_name
        save_with_image(trip, image_name, old_name)            # ...UPDATE the database row

        flash("Trip updated.", "success")
        return redirect(url_for("trip_detail", trip_id=trip.id))
    return render_template("trip_form.html", trip=trip, errors={},
                           values=trip.form_values(), page_title="Edit Trip")


@app.route("/trips/<int:trip_id>")
@login_required
def trip_detail(trip_id):
    """One trip's itinerary grouped by day, plus the budget panel.
    -> trip_detail.html. All totals come from properties on the Trip model."""
    trip = Trip.get_owned(trip_id, session["user_id"])
    if not trip:
        flash("Trip not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    return render_template("trip_detail.html", trip=trip,
                           grouped_activities=trip.activities_by_day())


@app.route("/completed")
@login_required
def completed_trips_page():
    """All finished trips, optionally filtered by ?search=... -> explore.html"""
    search = request.args.get("search", "").strip()
    trips = Trip.completed_for(session["user_id"], search=search)
    return render_template("explore.html", trips=trips, search=search)


# =============================================================================
# 6. ROUTES - ACTIVITIES
# =============================================================================
@app.route("/trips/<int:trip_id>/activities/new", methods=["GET", "POST"])
@login_required
def add_activity(trip_id):
    """Add an activity to one of the user's trips. -> activity_form.html"""
    trip = Trip.get_owned(trip_id, session["user_id"])
    if not trip:
        flash("Trip not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))

    if request.method == "POST":
        values, errors = Activity.validate(request.form, trip)
        data, ext = read_image_upload(errors)
        if errors:
            return render_template("activity_form.html", trip=trip, activity=None,
                                   errors=errors, values=request.form,
                                   page_title="Add Activity")

        image_name = pick_image_name(None, data, ext)
        activity = Activity(trip_id=trip.id, image_filename=image_name, **values)
        save_with_image(activity, image_name, None)

        flash("Activity added.", "success")
        return redirect(url_for("trip_detail", trip_id=trip.id))
    return render_template("activity_form.html", trip=trip, activity=None, errors={},
                           values={}, page_title="Add Activity")


@app.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
def edit_activity(activity_id):
    """Edit an activity. -> activity_form.html
    Activity.get_owned() joins to the trip, so you can only reach your own."""
    activity = Activity.get_owned(activity_id, session["user_id"])
    if not activity:
        flash("Activity not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    trip = activity.trip                      # relationship: the parent trip

    if request.method == "POST":
        values, errors = Activity.validate(request.form, trip)
        data, ext = read_image_upload(errors)
        if errors:
            return render_template("activity_form.html", trip=trip, activity=activity,
                                   errors=errors, values=request.form,
                                   page_title="Edit Activity")

        old_name = activity.image_filename
        image_name = pick_image_name(old_name, data, ext)
        activity.apply(values)
        activity.image_filename = image_name
        save_with_image(activity, image_name, old_name)

        flash("Activity updated.", "success")
        return redirect(url_for("trip_detail", trip_id=trip.id))
    return render_template("activity_form.html", trip=trip, activity=activity, errors={},
                           values=activity.form_values(), page_title="Edit Activity")


@app.route("/activities/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete_activity(activity_id):
    """Delete an activity and its photo. POST-only so a stray link can't delete."""
    activity = Activity.get_owned(activity_id, session["user_id"])
    if not activity:
        flash("Activity not found or you do not have access to it.", "error")
        return redirect(url_for("my_trips"))
    trip_id, photo = activity.trip_id, activity.image_filename
    activity.delete()                          # DELETE the row
    remove_image_file(photo)                   # then its photo file
    flash("Activity deleted.", "success")
    return redirect(url_for("trip_detail", trip_id=trip_id))


# =============================================================================
# 7. ROUTE - PHOTOS
# =============================================================================
@app.route("/media/<filename>")
@login_required
def media(filename):
    """Serve an uploaded photo, but only to the user who owns it.
    Used by every <img src="{{ url_for('media', filename=...) }}"> in the templates."""
    if not image_belongs_to_user(filename, session["user_id"]):
        abort(404)                             # also blocks "../" tricks: such names aren't in the DB
    response = send_from_directory(Config.UPLOAD_FOLDER, filename)
    response.headers["Cache-Control"] = "private, max-age=3600"   # cache in the browser only
    response.headers["X-Content-Type-Options"] = "nosniff"        # never guess the file type
    return response


# =============================================================================
# 8. ERROR PAGES (all show templates/error.html)
# =============================================================================
@app.errorhandler(400)
def bad_request(_error):
    """Raised by check_csrf() when the form token is missing or wrong."""
    return render_template("error.html", message="Your session expired or the form was invalid. "
                           "Please go back, refresh the page and try again."), 400


@app.errorhandler(404)
def not_found(_error):
    """Unknown URL, or a photo the user does not own."""
    return render_template("error.html", message="That page could not be found."), 404


@app.errorhandler(413)
def too_large(_error):
    """The upload was bigger than Config.MAX_CONTENT_LENGTH."""
    return render_template("error.html", message="That upload is too large. Images must be 5 MB or smaller."), 413


@app.errorhandler(500)
def server_error(_error):
    """Unexpected failure - most often a database problem."""
    return render_template("error.html", message="Something went wrong. Check the terminal and the database settings in config.py."), 500


# =============================================================================
# 9. START THE SERVER
# =============================================================================
if __name__ == "__main__":
    # Runs only when you type `python app.py` (not when another file imports app).
    # Debug mode auto-reloads on edits and shows detailed errors; use it only
    # while learning:  set FLASK_DEBUG=1
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
