"""Movie Night Planner - a simple Flask + MySQL project.

WHAT THE PROJECT DOES
    Users register, log in, propose (create) movies with a poster, like
    movies, and the movie with the most likes is the "Winning Movie".
    Only the person who created a movie can edit or delete it.

PROJECT FLOW (how the files connect)
    Browser  --->  app.py (route function)  --->  MySQL (schema.sql tables)
                        |                              |
                        |  validate()  checks input    |  get_rows() / change_data()
                        v                              v
                   templates/*.html  <---  data (movies, users)
                        |
                        +--> templates/base.html (page frame: top menu, flash
                             messages) <-- static/style.css (flat dark theme,
                             no background images)
                        +--> static/uploads/ (poster images saved by app.py)

    1. register()     -> validate("register") -> INSERT into users   -> login page
    2. login()        -> validate("login")    -> session["user_id"]  -> home
    3. home()         -> SELECT movies (search + genre filter)       -> home.html
    4. create_movie() -> validate("movie")    -> save poster + INSERT -> home
    5. like_movie()   -> add / remove your id in movies.likes (JSON)  -> same page
    6. edit_movie() / delete_movie() -> allowed ONLY for the creator
    7. winner()       -> top 3 movies by likes                       -> winner.html
    8. users()        -> every user + their movies (Delete = creator only)

SETTINGS live in the .env file (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD,
DB_NAME, SECRET_KEY). See .env.example.

All checking (validation) is done in ONE function: validate().
"""
import os
import secrets
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

import mysql.connector
from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort, session)
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()          # read the .env file next to app.py into os.environ

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
if app.secret_key == "change-this-secret-key":
    print("WARNING: set SECRET_KEY in the .env file before sharing this site.")

# ---- database settings come from the .env file (never hard-code passwords) ----
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "movie_night_db"),
}
# Safer session cookie: JavaScript cannot read it, and other websites
# cannot send it along with their own forms.
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  MAX_CONTENT_LENGTH=4 * 1024 * 1024)   # reject uploads over 4 MB
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
MAX_IMAGE_SIZE = 2 * 1024 * 1024            # 2 MB
ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg"]
GENRES = ["Sci-Fi", "Action", "Animation", "Comedy", "Drama", "Thriller", "Horror"]
RATINGS = ["U", "U/A", "A"]
MAX_GENRES = 3                      # a movie can have 1 to 3 genres


# ---------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------
def get_rows(sql, values=()):
    """Run a SELECT query and return the rows.

    Opens a MySQL connection (DB_CONFIG), runs the SQL, closes the
    connection. The values fill the %s signs separately from the SQL
    text, which stops SQL injection.

    Parameters:
        sql (str): the SELECT statement.
        values (tuple): values for the %s signs, in order.
    Returns:
        list of dict: one dictionary per row (empty list if none).
    """
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute(sql, values)
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return rows


def change_data(sql, values=()):
    """Run an INSERT / UPDATE / DELETE query and save the change.

    commit() makes MySQL keep the change permanently.

    Parameters:
        sql (str): the INSERT / UPDATE / DELETE statement.
        values (tuple): values for the %s signs, in order.
    Returns:
        int: id of the new row (useful after an INSERT).
    """
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()
    cursor.execute(sql, values)
    connection.commit()
    new_id = cursor.lastrowid
    cursor.close()
    connection.close()
    return new_id


# ---------------------------------------------------------------
# Security: login_required + CSRF token
# ---------------------------------------------------------------
def login_required(view):
    """Decorator: only logged-in users may open the page.

    Put @login_required under @app.route(...). If session["user_id"]
    is missing, the visitor is sent to the login page instead.

    Parameters:
        view (function): the page function to protect.
    Returns:
        function: a wrapped function that Flask calls instead.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        """Check the session, then run the real page or redirect."""
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    """Return this browser's secret CSRF token (created on first use).

    Every POST form has it in a hidden field ({{ csrf_token() }}), so
    other websites cannot submit our forms for a logged-in user.
    """
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    """Runs before EVERY request; rejects a POST with a wrong token (error 400)."""
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
            abort(400, "Invalid form token. Refresh the page and try again.")


# ---------------------------------------------------------------
# THE validation function (all checks are here)
# ---------------------------------------------------------------
def validate(kind, form, image=None, movie_id=0):
    """The ONE validation function: checks all submitted data.

    Parameters:
        kind (str): "register", "login" or "movie".
        form: the submitted form values (request.form).
        image: the uploaded poster file (movie only, optional).
        movie_id (int): id of the movie being edited (0 when creating),
            so a movie does not clash with its own title.
    Returns:
        tuple: (errors, data)
            errors - list of messages (empty list = everything is fine)
            data   - dictionary of cleaned values to refill the form
    """
    errors = []
    data = {}

    if kind in ("register", "login"):
        username = form.get("username", "").strip()
        password = form.get("password", "")
        data = {"username": username, "password": password}

        if kind == "login":
            if username == "" or password == "":
                errors.append("Enter your username and password.")
        else:
            if not (3 <= len(username) <= 30):
                errors.append("Username must be 3 to 30 characters.")
            elif not username.replace("_", "").isalnum():
                errors.append("Username can have only letters, numbers and _.")
            elif get_rows("SELECT id FROM users WHERE username = %s", (username,)):
                errors.append("That username is already taken.")
            if not (8 <= len(password) <= 128):
                errors.append("Password must be 8 to 128 characters.")
            if password != form.get("confirm_password", ""):
                errors.append("The two passwords do not match.")

    elif kind == "movie":
        title = form.get("title", "").strip()
        # genres come from a multi-select (several checkboxes named "genre");
        # keep them in the same order as GENRES and store them as "Sci-Fi,Drama"
        picked = form.getlist("genre")
        genres = [g for g in GENRES if g in picked]
        rating = form.get("rating", "")
        runtime = form.get("runtime", "").strip()
        synopsis = form.get("synopsis", "").strip()
        data = {"title": title, "genres": genres, "genre": ",".join(genres),
                "rating": rating, "runtime": runtime, "synopsis": synopsis}

        if not (2 <= len(title) <= 100):
            errors.append("Title must be 2 to 100 characters.")
        elif get_rows("SELECT id FROM movies WHERE title = %s AND id <> %s", (title, movie_id)):
            errors.append("This movie is already proposed.")
        if any(g not in GENRES for g in picked):
            errors.append("Choose genres from the list only.")
        elif not (1 <= len(genres) <= MAX_GENRES):
            errors.append("Choose 1 to %d genres." % MAX_GENRES)
        if rating not in RATINGS:
            errors.append("Choose a rating from the list.")
        if not runtime.isdigit() or not (1 <= int(runtime) <= 500):
            errors.append("Runtime must be a number between 1 and 500 minutes.")
        if not (10 <= len(synopsis) <= 240):
            errors.append("Synopsis must be 10 to 240 characters.")

        # optional poster image
        if image and image.filename != "":
            ext = image.filename.rsplit(".", 1)[-1].lower() if "." in image.filename else ""
            image.seek(0, os.SEEK_END)
            size = image.tell()
            image.seek(0)
            start = image.read(8)          # first bytes of a real PNG / JPG file
            image.seek(0)
            is_png = start.startswith(b"\x89PNG\r\n\x1a\n")
            is_jpg = start.startswith(b"\xff\xd8\xff")
            if ext not in ALLOWED_EXTENSIONS or not (is_png or is_jpg):
                errors.append("Poster must be a real PNG or JPG image.")
            elif size > MAX_IMAGE_SIZE:
                errors.append("Poster must be 2 MB or smaller.")

    return errors, data


def show_errors(errors):
    """Show every error message on the next page (red message box)."""
    for message in errors:
        flash(message, "error")


def movie_field_errors(errors):
    """Group movie validation messages so each appears below its form field."""
    field_errors = {"title": [], "genre": [], "rating": [], "runtime": [],
                    "synopsis": [], "poster": []}
    for message in errors:
        if message.startswith("Title ") or message == "This movie is already proposed.":
            field_errors["title"].append(message)
        elif message.startswith("Choose genres") or message.startswith("Choose 1 to"):
            field_errors["genre"].append(message)
        elif message.startswith("Choose a rating"):
            field_errors["rating"].append(message)
        elif message.startswith("Runtime "):
            field_errors["runtime"].append(message)
        elif message.startswith("Synopsis "):
            field_errors["synopsis"].append(message)
        elif message.startswith("Poster "):
            field_errors["poster"].append(message)
        else:
            # Keep unexpected validation messages visible rather than hiding them.
            field_errors["title"].append(message)
    return field_errors


# ---------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------
def save_poster(image):
    """Save an uploaded poster in static/uploads as DATE_TIME.ext.

    Parameters:
        image: the uploaded file (already checked by validate()).
    Returns:
        str: the new file name, which is stored in movies.poster.
    """
    ext = image.filename.rsplit(".", 1)[-1].lower()
    name = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "." + ext
    image.save(os.path.join(UPLOAD_FOLDER, name))
    return name


def remove_poster(name):
    """Delete a poster file from static/uploads (ignored if it is missing)."""
    if name:
        path = os.path.join(UPLOAD_FOLDER, name)
        if os.path.exists(path):
            os.remove(path)


# Likes live in ONE column: movies.likes, a JSON list of the ids of the
# users who liked the movie, e.g. ["1", "4"]. No separate likes table.
#   like_count = how many likes   liked = 1 if the logged-in user liked it
#   genres     = list made from the "Sci-Fi,Drama" text (added in movie_rows)
# The first %s (the logged-in user's id) is filled in by movie_rows().
MOVIE_SELECT = """
    SELECT m.id, m.user_id, m.title, m.genre, m.runtime, m.rating, m.synopsis,
           m.poster, u.username,
           JSON_LENGTH(m.likes) AS like_count,
           (JSON_SEARCH(m.likes, 'one', %s) IS NOT NULL) AS liked
    FROM movies m JOIN users u ON u.id = m.user_id
"""


def movie_rows(tail="", values=()):
    """Run MOVIE_SELECT plus a WHERE / ORDER BY tail and return movie dicts.

    Parameters:
        tail (str): extra SQL such as "WHERE m.id = %s ORDER BY ...".
        values (tuple): values for the %s signs inside tail.
    Returns:
        list of dict: movies with username, like_count, liked and genres.
    """
    me = str(session.get("user_id", 0))
    rows = get_rows(MOVIE_SELECT + tail, (me,) + tuple(values))
    for row in rows:
        row["genres"] = row["genre"].split(",")
    return rows


def get_movie(movie_id):
    """Find one movie by id (shows a 404 page if it does not exist).

    Returns:
        dict: the movie row with username, like_count, liked and genres.
    """
    rows = movie_rows(" WHERE m.id = %s", (movie_id,))
    if not rows:
        abort(404)
    return rows[0]


def is_owner(movie):
    """True only when the logged-in user is the one who created the movie."""
    return movie["user_id"] == session.get("user_id")


@app.context_processor
def template_helpers():
    """Make is_owner() usable inside every template: {% if is_owner(m) %}."""
    return {"is_owner": is_owner}


@app.after_request
def security_headers(response):
    """Add basic protective headers to every response.

    nosniff    - the browser must trust the file type we send (stops a
                 disguised upload from being run as a script).
    DENY       - other websites cannot show our pages inside a frame
                 (stops click-jacking).
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


def go_back(default="home"):
    """Redirect to the page the user came from, but ONLY if it is on this site.

    A forged Referer header pointing to another website is ignored (that
    would be an open redirect), and the user goes to the default page.
    """
    came_from = request.referrer or ""
    if came_from and urlparse(came_from).netloc == request.host:
        return redirect(came_from)
    return redirect(url_for(default))


# ---------------------------------------------------------------
# Account routes  (templates: register.html, login.html)
# ---------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register page: create a new account.

    GET  -> show the empty form (register.html).
    POST -> validate("register"); if OK, save the username and a HASH of
            the password (never the real password) in the users table,
            then go to the login page.
    """
    if "user_id" in session:
        return redirect(url_for("home"))
    username = ""
    if request.method == "POST":
        errors, data = validate("register", request.form)
        username = data["username"]
        if not errors:
            try:
                change_data("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                            (username, generate_password_hash(data["password"])))
                flash("Account created. Please log in.")
                return redirect(url_for("login"))
            except mysql.connector.IntegrityError:   # UNIQUE username safety net
                errors.append("That username is already taken.")
        show_errors(errors)
    return render_template("register.html", username=username, page="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page: check username + password and start a session.

    On success the user's id is stored in the session (that is what
    "logged in" means) and the user goes to the home page. The same
    message is shown for a wrong username or password, so nobody can
    find out which usernames exist.
    """
    if "user_id" in session:
        return redirect(url_for("home"))
    username = ""
    if request.method == "POST":
        errors, data = validate("login", request.form)
        username = data["username"]
        if not errors:
            rows = get_rows("SELECT id, username, password_hash FROM users WHERE username = %s",
                            (username,))
            if rows and check_password_hash(rows[0]["password_hash"], data["password"]):
                session.clear()
                session["user_id"] = rows[0]["id"]
                session["username"] = rows[0]["username"]
                flash("Welcome, " + rows[0]["username"] + "!")
                return redirect(url_for("home"))
            errors.append("Incorrect username or password.")
        show_errors(errors)
    return render_template("login.html", username=username, page="login")


@app.route("/logout", methods=["POST"])
def logout():
    """Log out: clear the session (POST only) and go to the login page."""
    session.clear()
    flash("You have logged out.")
    return redirect(url_for("login"))


# ---------------------------------------------------------------
# Movie routes  (templates: home.html, details.html, movie_form.html, winner.html)
# ---------------------------------------------------------------
@app.route("/")
@login_required
def home():
    """Home page: movie cards with a search box and a genre filter.

    The search text matches the movie title or the creator's name.
    Movies are listed with the most-liked first.
    """
    search = request.args.get("search", "").strip()[:100]
    genre = request.args.get("genre", "")
    like = "%" + search + "%"
    movies = movie_rows(
        """ WHERE (m.title LIKE %s OR u.username LIKE %s)
            AND (%s = '' OR FIND_IN_SET(%s, m.genre))
            ORDER BY like_count DESC, m.id DESC""",
        (like, like, genre, genre))

    # ---- Live Ballot Tracker (sidebar): top 3 of ALL movies ----
    top = movie_rows(" ORDER BY like_count DESC, m.id ASC LIMIT 3")
    total = int(get_rows("SELECT COALESCE(SUM(JSON_LENGTH(likes)), 0) AS n FROM movies")[0]["n"])
    for movie in top:
        # equal likes share a rank (1, 1, 3)
        movie["rank"] = 1 + sum(1 for other in top if other["like_count"] > movie["like_count"])
        movie["percent"] = round(movie["like_count"] * 100 / total) if total else 0
    tie = len(top) > 1 and top[0]["like_count"] > 0 and top[0]["like_count"] == top[1]["like_count"]
    my_likes = get_rows("""SELECT title FROM movies
                           WHERE JSON_SEARCH(likes, 'one', %s) IS NOT NULL ORDER BY id""",
                        (str(session["user_id"]),))
    return render_template("home.html", movies=movies, genres=GENRES,
                           search=search, genre=genre, page="home",
                           top=top, total=total, tie=tie, my_likes=my_likes)


@app.route("/movies/<int:movie_id>")
@login_required
def details(movie_id):
    """Details page: big poster, synopsis, likes, and Edit/Delete for the creator."""
    return render_template("details.html", movie=get_movie(movie_id), page="home")


@app.route("/movies/new", methods=["GET", "POST"])
@login_required
def create_movie():
    """Create Movie page: propose a new movie (poster is optional).

    POST -> validate("movie"); if OK, save the poster file (if any) and
            INSERT the movie with the logged-in user as its creator.
    """
    movie = {"title": "", "genre": "", "genres": [], "rating": RATINGS[0],
             "runtime": "", "synopsis": "", "poster": None}
    if request.method == "POST":
        image = request.files.get("poster")
        errors, movie = validate("movie", request.form, image)
        if not errors:
            poster = save_poster(image) if image and image.filename else None
            change_data("""INSERT INTO movies (user_id, title, genre, runtime, rating, synopsis, poster, likes)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, '[]')""",
                        (session["user_id"], movie["title"], movie["genre"],
                         int(movie["runtime"]), movie["rating"], movie["synopsis"], poster))
            flash("Movie created!")
            return redirect(url_for("home"))
        movie["poster"] = None
        field_errors = movie_field_errors(errors)
    else:
        field_errors = {}
    return render_template("movie_form.html", movie=movie, genres=GENRES,
                           ratings=RATINGS, max_genres=MAX_GENRES, editing=False,
                           field_errors=field_errors, page="create")


@app.route("/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@login_required
def edit_movie(movie_id):
    """Edit page: change a movie. ONLY its creator is allowed.

    Anyone else is sent back to the details page with a message.
    A new poster replaces (and deletes) the old poster file.
    """
    movie = get_movie(movie_id)
    if not is_owner(movie):
        flash("You can edit only the movies you created.", "error")
        return redirect(url_for("details", movie_id=movie_id))
    if request.method == "POST":
        image = request.files.get("poster")
        errors, data = validate("movie", request.form, image, movie_id)
        if not errors:
            poster = movie["poster"]
            if image and image.filename:
                remove_poster(poster)
                poster = save_poster(image)
            change_data("""UPDATE movies SET title=%s, genre=%s, runtime=%s, rating=%s,
                           synopsis=%s, poster=%s WHERE id=%s""",
                        (data["title"], data["genre"], int(data["runtime"]), data["rating"],
                         data["synopsis"], poster, movie_id))
            flash("Movie updated.")
            return redirect(url_for("details", movie_id=movie_id))
        movie.update(data)
        field_errors = movie_field_errors(errors)
    else:
        field_errors = {}
    return render_template("movie_form.html", movie=movie, genres=GENRES,
                           ratings=RATINGS, max_genres=MAX_GENRES, editing=True,
                           field_errors=field_errors, page="home")


@app.route("/movies/<int:movie_id>/delete", methods=["POST"])
@login_required
def delete_movie(movie_id):
    """Delete a movie (POST only). ONLY its creator is allowed.

    Another user's movie is never deleted: they get an error message.
    The likes go with the movie row (they are a column of it) and its
    poster file is removed from static/uploads. The hidden form field
    "back" decides where to return (the Users page or the home page).
    """
    movie = get_movie(movie_id)
    if not is_owner(movie):
        flash("You can delete only the movies you created.", "error")
        return redirect(url_for("details", movie_id=movie_id))
    change_data("DELETE FROM movies WHERE id = %s", (movie_id,))
    remove_poster(movie["poster"])
    flash("Movie deleted.")
    if request.form.get("back") == "users":      # deleted from the Users page
        return redirect(url_for("users"))
    return redirect(url_for("home"))


@app.route("/movies/<int:movie_id>/like", methods=["POST"])
@login_required
def like_movie(movie_id):
    """Like / unlike a movie (POST only).

    Likes are stored in the movies.likes column (a JSON list of user ids).
    If the user's id is already in the list it is removed, otherwise it
    is added. Both are ONE atomic UPDATE, so two quick clicks cannot
    count twice. Then the user returns to the page they came from.
    """
    movie = get_movie(movie_id)
    me = str(session["user_id"])
    if movie["liked"]:
        change_data("""UPDATE movies
                       SET likes = JSON_REMOVE(likes, JSON_UNQUOTE(JSON_SEARCH(likes, 'one', %s)))
                       WHERE id = %s AND JSON_SEARCH(likes, 'one', %s) IS NOT NULL""",
                    (me, movie_id, me))
    else:
        change_data("""UPDATE movies SET likes = JSON_ARRAY_APPEND(likes, '$', %s)
                       WHERE id = %s AND JSON_SEARCH(likes, 'one', %s) IS NULL""",
                    (me, movie_id, me))
    return go_back("home")


@app.route("/users")
@login_required
def users():
    """Users page: every registered user with the movies they created.

    Each movie row has a Delete button, but the template shows it ONLY
    when the logged-in user created that movie (is_owner()).
    """
    people = get_rows("SELECT id, username FROM users ORDER BY username")
    movies = movie_rows(" ORDER BY m.id DESC")
    for person in people:
        person["movies"] = [m for m in movies if m["user_id"] == person["id"]]
    return render_template("users.html", people=people, page="users")


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
def show_error(error):
    """Friendly error page (bad form token, not found, file too big...)."""
    messages = {413: "That file is too large (maximum 4 MB)."}
    text = messages.get(error.code, error.description)
    return render_template("error.html", code=error.code, text=text, page=""), error.code


@app.errorhandler(mysql.connector.Error)
def database_error(error):
    """Friendly page when MySQL is off or the password in DB_CONFIG is wrong.

    The real technical message goes to the console (for you), never to the
    visitor's browser.
    """
    app.logger.error("Database error: %s", error)
    return render_template("error.html", code=503, page="",
                           text="The database is not available right now. Please try again."), 503


@app.route("/winner")
@login_required
def winner():
    """Winning Movie page: the most-liked movie plus a top-3 leaderboard.

    On a tie the movie that was proposed first wins (lowest id).
    """
    movies = movie_rows(" ORDER BY like_count DESC, m.id ASC LIMIT 3")
    return render_template("winner.html", movies=movies, page="winner")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
