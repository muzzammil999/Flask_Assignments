"""Community Event Manager - a very simple Flask + MySQL project (with login).

How this project works
----------------------
1. All data is stored in a MySQL database (created with schema.sql in
   MySQL Workbench). There are three tables:
       events         -> one row for each event
       registrations  -> one row for each registration
       users          -> one row for each person who can log in  (NEW)
2. Python talks to MySQL with the "mysql-connector-python" package and
   plain SQL queries (SELECT, INSERT, UPDATE, DELETE).
3. All form checking (validation) is done here in Python, not in HTML.
4. Uploaded images are saved in the folder static/uploads. Each image is
   named with the DATE + TIME of the upload, for example
   20261004_104530.jpg, and that name is saved in the database column
   events.image_filename.
5. The search/filter panel on the home page filters events in MySQL
   (title/venue search, category, upcoming only).

How the security (login) works  (NEW)
-------------------------------------
1. SIGN UP  : the password is turned into a "hash" (a scrambled text that
               cannot be reversed) and only the hash is saved in MySQL.
2. LOG IN   : the typed password is checked against the saved hash. If it
               matches, the user's id is stored in Flask's "session"
               (a small signed cookie kept by the browser).
3. PROTECTED PAGES: the @login_required decorator looks in the session.
               No user id -> the visitor is sent to the login page.
4. CSRF TOKEN: every POST form carries a secret random token. A POST
               without the correct token is rejected, so other websites
               cannot submit our forms for a logged-in user.
5. LOG OUT  : the whole session is cleared.

Pages (routes)
--------------
    /                           -> home page (list of events)         public
    /events/<id>                -> event details                      public
    /signup                     -> create a new account               public
    /login                      -> log in                             public
    /logout                     -> log out (POST only)                public
    /events/new                 -> create a new event                 LOGIN REQUIRED
    /events/<id>/edit           -> edit an event                      LOGIN REQUIRED
    /events/<id>/register       -> register seats for an event        LOGIN REQUIRED
    /events/<id>/delete         -> delete an event (POST only)        LOGIN REQUIRED
"""

import os
import secrets
from datetime import datetime, date
from functools import wraps

import mysql.connector
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort, session)
from werkzeug.security import generate_password_hash, check_password_hash

# Create the Flask application object.
app = Flask(__name__)

# ------------------------------------------------------------------
# Security settings
# ------------------------------------------------------------------
# The secret key is used by Flask to SIGN the session cookie. Because of
# the signature, a user cannot edit the cookie (for example change the
# user id to someone else's) without Flask noticing.
# os.environ.get("SECRET_KEY", "...") means: use the environment variable
# SECRET_KEY if it exists, otherwise use the demo text after the comma.
# The demo text is fine on your own computer, but if the project is ever
# put on a real server you MUST set a long random SECRET_KEY.
app.secret_key = os.environ.get("SECRET_KEY", "demo-key-change-before-sharing")

# HTTPONLY: JavaScript in the page cannot read the session cookie.
# SAMESITE "Lax": the browser does not send the cookie when another
# website submits a POST form to us (an extra shield against CSRF).
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# ------------------------------------------------------------------
# Settings (constants)
# ------------------------------------------------------------------

# MySQL connection details. CHANGE the user and password to the same
# ones you use to log in to MySQL Workbench.
# (The password can also come from an environment variable called
# DB_PASSWORD, which is safer than writing it in the code.)
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.environ.get("DB_PASSWORD", "Chinna@9999"),
    "database": "CE1",
}

# Folder where uploaded event images are saved: static/uploads
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")

# Maximum image size allowed: 2 MB written in bytes (2 * 1024 * 1024).
MAX_IMAGE_SIZE = 2 * 1024 * 1024

# The only categories a user can choose from.
CATEGORIES = ["Workshop", "Community", "Career"]

# Image file types we accept.
ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg"]

# Rules for usernames and passwords (used by validate_signup).
USERNAME_MIN, USERNAME_MAX = 3, 30
PASSWORD_MIN, PASSWORD_MAX = 8, 128


# ==================================================================
# Database functions
# ==================================================================

def get_rows(sql, values=()):
    """Run a SELECT query and return all the rows found.

    Explanation:
        1. Open a connection to MySQL using DB_CONFIG.
        2. Run the SQL. The values are sent separately from the SQL text
           and fill the %s signs. This is what stops "SQL injection":
           MySQL always treats the values as plain data, never as SQL.
        3. Read all rows, close the connection and return the rows.
        dictionary=True makes every row a dictionary, so we can write
        row["title"] instead of remembering column numbers.

    Parameters:
        sql (str): the SELECT statement.
        values (tuple): the values for the %s signs, in order.

    Returns:
        list: a list of dictionaries (empty list if nothing was found).
    """
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute(sql, values)
    rows = cursor.fetchall()          # read every row of the result
    cursor.close()
    connection.close()
    return rows


def change_data(sql, values=()):
    """Run an INSERT, UPDATE or DELETE query and save the change.

    Explanation:
        Works like get_rows(), but these queries do not return rows.
        commit() is very important: without it MySQL does NOT save the
        change permanently.

    Parameters:
        sql (str): the INSERT / UPDATE / DELETE statement.
        values (tuple): the values for the %s signs, in order.

    Returns:
        int: the id of the new row (only useful after an INSERT).
    """
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()
    cursor.execute(sql, values)
    connection.commit()               # save the change in the database
    new_id = cursor.lastrowid         # id MySQL gave to the inserted row
    cursor.close()
    connection.close()
    return new_id


# ==================================================================
# Security functions (NEW)
# ==================================================================

def login_required(view):
    """Decorator: only let a logged-in user open the page.

    Explanation:
        A decorator is a function that wraps another function. Put
        @login_required directly under @app.route(...) and Flask will
        run the check below BEFORE the real page function:

            @app.route("/events/new")
            @login_required
            def create_event(): ...

        The check: a logged-in user has "user_id" inside the session
        (it is put there by login()). If it is missing, we show a
        message and send the visitor to the login page. For a normal
        page (GET) we also remember the page they wanted in "next", so
        after logging in they come back to it.

    Parameters:
        view (function): the page function we want to protect.

    Returns:
        function: a new function ("wrapped") that Flask calls instead
        of the original one.
    """
    @wraps(view)   # keeps the original function's name so Flask routes still work
    def wrapped(*args, **kwargs):
        """Check the session, then run the real page or redirect to login.

        Explanation:
            *args and **kwargs simply pass along whatever the route
            gives us (for example event_id) to the real page function.

        Returns:
            The real page's response, or a redirect to the login page.
        """
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            # Only remember the page for GET requests. A POST page (like
            # delete) cannot be opened again by a plain link.
            if request.method == "GET":
                return redirect(url_for("login", next=request.path))
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    """Get this browser's CSRF token (create it the first time).

    Explanation:
        CSRF = "Cross-Site Request Forgery": a bad website tries to make
        YOUR browser submit a form to OUR site while you are logged in.
        The defence: every form of ours contains a hidden random token
        that also lives in the session. A bad site cannot read our
        pages, so it cannot know the token.
        secrets.token_urlsafe(32) makes a long unpredictable text.
        Templates call this function as {{ csrf_token() }}.

    Returns:
        str: the token stored in session["csrf_token"].
    """
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


# Make csrf_token() available inside every HTML template.
app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    """Reject every POST request that does not carry the correct token.

    Explanation:
        @app.before_request makes Flask run this function before EVERY
        request, so no POST route can forget the check. We compare the
        token submitted in the form with the token saved in the session.
        If they differ (or are missing) we stop with error 400 and the
        route function never runs.
        compare_digest() compares in constant time, so an attacker
        cannot learn the token by measuring how fast the answer is.
        We encode both texts to bytes first, because compare_digest
        crashes on texts that contain non-English characters.

    Returns:
        None when the request is fine (Flask continues normally).
    """
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
            abort(400, "Invalid form token. Go back, refresh the page and try again.")


def get_safe_next(target):
    """Make sure the "go back to" address after login stays on OUR site.

    Explanation:
        After login we redirect to the page in the "next" value. If we
        trusted it blindly, an attacker could send a link such as
        /login?next=https://evil.example and, after a real login, our
        site would send the user to the fake site ("open redirect").
        We only accept addresses that start with a single "/", which
        means "a page on this same website".

    Parameters:
        target (str): the "next" text from the URL or form.

    Returns:
        str: target if it is safe, otherwise the home page address.
    """
    if target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("home")


def validate_signup(form):
    """Check the sign-up form.

    Explanation:
        Rules: username 3-30 characters (letters, numbers, underscore),
        not already used; password 8-128 characters; the two password
        boxes must match. The password is NOT stripped, because spaces
        can be part of a password.

    Parameters:
        form: the submitted form values (request.form).

    Returns:
        tuple: (errors, data)
            errors - list of error messages (empty if all is fine)
            data   - dictionary with the cleaned "username" and the
                     typed "password"
    """
    errors = []

    username = form.get("username", "").strip()
    password = form.get("password", "")
    confirm = form.get("confirm_password", "")

    if not (USERNAME_MIN <= len(username) <= USERNAME_MAX):
        errors.append("Username must be " + str(USERNAME_MIN) + " to "
                      + str(USERNAME_MAX) + " characters long.")
    elif not username.replace("_", "").isalnum():
        errors.append("Username can contain only letters, numbers and underscore (_).")
    else:
        # Ask MySQL if the name is already taken.
        old = get_rows("SELECT id FROM users WHERE username = %s", (username,))
        if len(old) > 0:
            errors.append("That username is already taken.")

    if not (PASSWORD_MIN <= len(password) <= PASSWORD_MAX):
        errors.append("Password must be " + str(PASSWORD_MIN) + " to "
                      + str(PASSWORD_MAX) + " characters long.")

    if password != confirm:
        errors.append("The two passwords do not match.")

    data = {"username": username, "password": password}
    return errors, data


# ==================================================================
# Helper functions
# ==================================================================

def fix_event(event):
    """Prepare an event row from MySQL so the templates can use it.

    Explanation:
        MySQL gives us the start time in a form that cannot be printed
        as "10:00 AM", so we convert it to a normal time object.
        We also calculate two extra values used by the templates:
        "available_seats" and "percentage" (for the progress bar).
        These two are NOT stored in the database, because they can
        always be worked out from the capacity and the booked seats.

    Parameters:
        event (dict): one row from the events table.

    Returns:
        dict: the same dictionary with the fixed/extra values.
    """
    # str(...) gives "10:00:00", and strptime turns that text into a time.
    event["start_time"] = datetime.strptime(str(event["start_time"]), "%H:%M:%S").time()

    # available seats = total seats - seats already booked
    event["available_seats"] = event["seat_capacity"] - event["booked_seats"]

    # percentage of seats that are booked (used for the progress bar)
    event["percentage"] = round(event["booked_seats"] / event["seat_capacity"] * 100)
    return event


def get_event(event_id):
    """Find one event in the database using its id.

    Explanation:
        Many routes (details, edit, register, delete) need one event.
        We ask MySQL for the row with this id. If no row is found, the
        user is shown a 404 "Not Found" page.

    Parameters:
        event_id (int): the id of the event we are looking for.

    Returns:
        dict: the matching event (already fixed by fix_event).
    """
    rows = get_rows("SELECT * FROM events WHERE id = %s", (event_id,))

    # Empty list -> no event has this id.
    if len(rows) == 0:
        abort(404)

    return fix_event(rows[0])


def parse_date(text):
    """Convert text like '2026-10-05' into a date object.

    Explanation:
        Form values always arrive as text. We need a real date so we
        can compare dates and save them in MySQL.

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
        errors (list): list of error messages (strings).
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
        The links point to the first event in the database. If there
        are no events, they point to the home page.

    Returns:
        dict: the variables "nav_details" and "nav_register".
    """
    rows = get_rows("SELECT id FROM events ORDER BY id LIMIT 1")

    if len(rows) > 0:
        first_id = rows[0]["id"]
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


def save_image(image):
    """Save the uploaded image and return its new name.

    Explanation:
        The new file name is made from the current DATE + TIME + the
        original file extension:

            date + time + extension  ->  20261004_104530.jpg
                                         (year month day _ hour minute second)

        The file is saved inside static/uploads, and the returned name
        is what we store in the database column events.image_filename.
        We never use the name the user's computer gave the file, so a
        tricky file name (like "../../app.py") can do no harm.

    Parameters:
        image: the uploaded file object (or None).

    Returns:
        str: the saved file name, or None if no image was uploaded.
    """
    # No file chosen -> nothing to save.
    if image is None or image.filename == "":
        return None

    # Current date and time as text, e.g. "20261004_104530".
    now_text = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Final name = date + time + "." + extension.
    filename = now_text + "." + get_extension(image.filename)

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
        before for this event (checked in the registrations table).

    Parameters:
        form: the submitted form values (request.form).
        event (dict): the event the person wants to join.

    Returns:
        tuple: (errors, data)
            errors - list of error messages (empty if all is fine)
            data   - dictionary with the cleaned name, email, mobile
                     and seats
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

    # Ask MySQL if this email already registered for this event.
    old = get_rows("SELECT id FROM registrations WHERE event_id = %s AND email = %s",
                   (event["id"], email))
    if len(old) > 0:
        errors.append("This email has already registered for this event.")

    data = {"name": name, "email": email, "mobile": mobile, "seats": seats}
    return errors, data


# ==================================================================
# Routes - login, sign up, log out (NEW)
# ==================================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Sign-up page: create a new account.

    Explanation:
        GET  -> show the empty sign-up form.
        POST -> validate the form. If it is valid:
                1. turn the password into a hash with
                   generate_password_hash() (it adds a random "salt"
                   and is deliberately slow, so guessing is hard)
                2. INSERT only the username and the HASH into MySQL
                   - the real password is never saved anywhere
                3. send the user to the login page
        The UNIQUE column in MySQL is the final guard: if two people
        pick the same name at the same moment, MySQL refuses the second
        one and we show the "already taken" message.

    Returns:
        The signup.html page, or a redirect to the login page.
    """
    # A logged-in user does not need this page.
    if "user_id" in session:
        return redirect(url_for("home"))

    username = ""   # keeps the typed name in the box if there are errors

    if request.method == "POST":
        errors, data = validate_signup(request.form)
        username = data["username"]

        if len(errors) == 0:
            password_hash = generate_password_hash(data["password"])
            try:
                change_data("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                            (data["username"], password_hash))
            except mysql.connector.IntegrityError:
                # Raised by MySQL when the UNIQUE username rule is broken.
                errors.append("That username is already taken.")
            else:
                flash("Account created. Please log in.")
                return redirect(url_for("login"))

        show_errors(errors)

    return render_template("signup.html", username=username, page="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page: check the username and password, then start a session.

    Explanation:
        GET  -> show the login form.
        POST -> 1. find the user row by username
                2. check_password_hash() hashes the typed password the
                   same way and compares it with the saved hash
                3. if it matches: session.clear() first (so no old
                   session data is reused), then save the user's id and
                   name in the session, and redirect
                4. if not: show ONE message for both "no such user" and
                   "wrong password", so an attacker cannot find out
                   which usernames exist.
        "next" (from the URL or a hidden field) is the page the user
        originally wanted; get_safe_next() makes sure it is a page on
        our own site.

    Returns:
        The login.html page, or a redirect after a successful login.
    """
    # A logged-in user does not need this page.
    if "user_id" in session:
        return redirect(url_for("home"))

    next_url = request.values.get("next", "")   # works for URL and form
    username = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        rows = get_rows("SELECT id, username, password_hash FROM users WHERE username = %s",
                        (username,))

        if len(rows) == 0 or not check_password_hash(rows[0]["password_hash"], password):
            flash("Incorrect username or password.", "error")
        else:
            user = rows[0]
            session.clear()                      # start from a fresh session
            session["user_id"] = user["id"]      # this line = "logged in"
            session["username"] = user["username"]
            flash("Welcome, " + user["username"] + "!")
            return redirect(get_safe_next(next_url))

    return render_template("login.html", username=username, next_url=next_url, page="login")


@app.route("/logout", methods=["POST"])
def logout():
    """Log out: remove everything from the session.

    Explanation:
        Only POST is allowed. If logout were a normal link (GET), any
        website could log you out just by showing a hidden image that
        points to /logout. As a POST form it also needs the CSRF token.
        session.clear() removes user_id, username and the CSRF token.
        We flash the message AFTER clearing, because flash messages are
        also stored in the session.

    Returns:
        A redirect to the home page.
    """
    session.clear()
    flash("You have logged out.")
    return redirect(url_for("home"))


# ==================================================================
# Routes - events
# ==================================================================

@app.route("/")
def home():
    """Home page: show events, optionally filtered, sorted by date and time.

    Explanation:
        The filter form on the page sends its values in the URL
        (for example /?search=yoga&category=Workshop&upcoming=1).
        We read them here and build the WHERE part of the SQL query.
        Values are always passed as %s parameters (never glued into the
        SQL text), so the search box cannot be used for SQL injection.

        search    -> text found in the title OR the venue
        category  -> must be one of CATEGORIES, otherwise it is ignored
        upcoming  -> only events whose date is today or later

    Returns:
        The rendered index.html page.
    """
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    upcoming = request.args.get("upcoming") == "1"

    # Only accept a category we know about.
    if category not in CATEGORIES:
        category = ""

    conditions = []
    values = []

    if search:
        conditions.append("(title LIKE %s OR venue LIKE %s)")
        like = "%" + search + "%"
        values.extend([like, like])

    if category:
        conditions.append("category = %s")
        values.append(category)

    if upcoming:
        conditions.append("event_date >= CURDATE()")

    sql = "SELECT * FROM events"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY event_date, start_time"

    rows = get_rows(sql, tuple(values))

    events = []
    for row in rows:
        events.append(fix_event(row))

    filters = {"search": search, "category": category, "upcoming": upcoming}
    is_filtered = bool(search or category or upcoming)

    return render_template("index.html", events=events, page="home",
                           categories=CATEGORIES, filters=filters,
                           is_filtered=is_filtered)


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
@login_required
def create_event():
    """Create page: show the new-event form and save the event.

    Explanation:
        Protected by @login_required: visitors who are not logged in
        are sent to the login page.
        GET  -> show an empty form.
        POST -> the form was submitted:
                1. validate the fields and the image
                2. if there are errors, show them and show the form again
                   (the typed values are kept)
                3. if all is fine, INSERT the event into MySQL and go to
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
            # Save the image file; we get back its name (or None).
            image_name = save_image(image)

            # booked_seats starts at 0 because nobody has booked yet.
            sql = ("INSERT INTO events (title, category, event_date, start_time, venue, "
                   "seat_capacity, booked_seats, organizer_email, registration_deadline, "
                   "description, image_filename) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            values = (data["title"], data["category"], data["event_date"],
                      data["start_time"], data["venue"], data["seat_capacity"], 0,
                      data["organizer_email"], data["registration_deadline"],
                      data["description"], image_name)
            change_data(sql, values)

            flash("Event published successfully. Your new event now appears in the list.")
            return redirect(url_for("home"))

        # There were errors -> show them (page is shown again below).
        show_errors(errors)

    return render_template("create.html", form=form, categories=CATEGORIES, page="create")


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def edit_event(event_id):
    """Edit page: show the event form and update the event.

    Explanation:
        Protected by @login_required.
        GET  -> show the form filled with the current event values.
        POST -> validate the new values. The capacity cannot be lower
                than the seats already booked. If the image field is
                empty, the old image name stays in the database.

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
            # Start with the old image name; replace it only if the
            # user chose a new image.
            image_name = event["image_filename"]
            new_image = save_image(image)
            if new_image is not None:
                image_name = new_image

            sql = ("UPDATE events SET title = %s, category = %s, event_date = %s, "
                   "start_time = %s, venue = %s, seat_capacity = %s, "
                   "organizer_email = %s, registration_deadline = %s, "
                   "description = %s, image_filename = %s WHERE id = %s")
            values = (data["title"], data["category"], data["event_date"],
                      data["start_time"], data["venue"], data["seat_capacity"],
                      data["organizer_email"], data["registration_deadline"],
                      data["description"], image_name, event_id)
            change_data(sql, values)

            flash("Event updated successfully!")
            return redirect(url_for("event_details", event_id=event_id))

        show_errors(errors)

    return render_template("edit.html", event=event, form=form,
                           categories=CATEGORIES, page="edit")


@app.route("/events/<int:event_id>/register", methods=["GET", "POST"])
@login_required
def register_event(event_id):
    """Register page: reserve seats for an event.

    Explanation:
        Protected by @login_required.
        GET  -> show the registration form (1 seat selected).
        POST -> validate the form. If it is valid, two things are saved:
                1. a new row in the registrations table
                2. booked_seats of the event is increased

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
            # 1. Save the registration.
            change_data("INSERT INTO registrations (event_id, full_name, email, mobile, seats) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (event_id, data["name"], data["email"], data["mobile"], data["seats"]))

            # 2. Add the requested seats to the booked seats.
            change_data("UPDATE events SET booked_seats = booked_seats + %s WHERE id = %s",
                        (data["seats"], event_id))

            flash("Registered " + str(data["seats"]) + " seat(s) successfully!")
            return redirect(url_for("event_details", event_id=event_id))

        show_errors(errors)

    return render_template("register.html", event=event, form=form, page="register")


@app.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
def delete_event(event_id):
    """Delete an event and all its registrations.

    Explanation:
        Protected by @login_required, and only POST is allowed (no GET),
        so an event can never be deleted just by opening a link. The
        delete button on the home page is a small form that sends a
        POST request together with the CSRF token.
        The registrations must be deleted FIRST, because they point to
        the event (foreign key). MySQL will not delete an event while
        registrations still use it.

    Parameters:
        event_id (int): id of the event to delete (from the URL).

    Returns:
        A redirect to the home page.
    """
    event = get_event(event_id)   # shows 404 if the event does not exist

    change_data("DELETE FROM registrations WHERE event_id = %s", (event_id,))
    change_data("DELETE FROM events WHERE id = %s", (event_id,))

    flash("Event '" + event["title"] + "' deleted.")
    return redirect(url_for("home"))


# Run the development server only when this file is started directly
# with "python app.py".
# debug=True is only for learning on your own computer (auto-reload and
# detailed error pages). NEVER leave it on for a real website.
if __name__ == "__main__":
    app.run(debug=True)
