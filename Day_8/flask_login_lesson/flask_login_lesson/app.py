"""A small Flask app demonstrating login sessions and CSRF-protected forms.

Flask reads session data from the browser's signed session cookie at the start
of a request, and sends an updated cookie when the session changes in a response.
"""

# Standard-library tools used for configuration, secure tokens, and the database.
import os  # Read configuration such as SECRET_KEY from environment variables.
import secrets  # Generate unpredictable values, including CSRF tokens.
import sqlite3  # Use the built-in SQLite database driver.
from functools import wraps  # Preserve a view's metadata when applying a decorator.
from pathlib import Path  # Build file paths safely across operating systems.

# Flask tools for routing requests, reading form/session data, and returning responses.
from flask import (
    Flask,  # Create the web application.
    abort,  # Stop a request with an HTTP error response.
    flash,  # Store a one-time message to show after a redirect.
    g,  # Store data, such as a database connection, for the current request.
    redirect,  # Tell the browser to visit another URL.
    render_template,  # Render an HTML template into a response.
    request,  # Read the current incoming request and submitted form.
    session,  # Read or update data associated with this browser's session.
    url_for,  # Build a URL from a Flask route's function name.
)
# Helpers for safely storing password hashes instead of plain-text passwords.
from werkzeug.security import (
    check_password_hash,  # Compare a submitted password with its stored hash.
    generate_password_hash,  # Hash a password before saving it to the database.
)

BASE = Path(__file__).resolve().parent
app = Flask(__name__)
# Flask's default session is stored in a browser cookie and signed with this key.
# It is tamper-resistant, not encrypted, so do not put passwords or secrets in it.
app.secret_key = os.environ.get('SECRET_KEY', 'classroom-only-change-before-sharing')
# These cookie settings add protection when the browser sends the session cookie.
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
DB = BASE / 'classroom.db'
CATEGORIES = ('Books', 'Electronics', 'Other')


def database():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

# This is Flask’s cleanup function for the database connection:
# @app.teardown_appcontext tells Flask to call this function when the current application context ends, 
# typically after a request finishes. Flask also calls it when handling an error.
@app.teardown_appcontext
def close_database(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB) as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL,
                name TEXT NOT NULL, category TEXT NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
        ''')


def login_required(view):
    """Redirect visitors to login unless their session has a user ID.
    wrapped is a replacement function that Flask calls instead of the original route. 
    *args and **kwargs let it accept the same arguments the route might receive.
    @wraps(view) preserves the original function’s name and metadata, which helps Flask identify the route correctly."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    """Get this session's CSRF token, creating one on the first request if needed.

    Templates include this value in POST forms. The request check below compares
    the submitted value with the copy kept in this browser's Flask session.
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def check_csrf():
    """Reject POST requests whose form token does not match this session.

    A legitimate form submits both its fields and the session's random token.
    A cross-site form can cause a browser to send cookies, but should not know
    this token. Comparing the values helps distinguish the legitimate request.
    """
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        expected = session.get('csrf_token', '')
        if not expected or not secrets.compare_digest(supplied, expected):
            abort(400, 'Invalid form token. Refresh the page and try again.')


@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not 3 <= len(username) <= 30 or len(password) < 8:
            flash('Username: 3–30 characters. Password: at least 8 characters.')
        else:
            try:
                database().execute(
                    'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                    (username, generate_password_hash(password)),
                )
                database().commit()
            except sqlite3.IntegrityError:
                flash('That username is already taken.')
            else:
                flash('Account created. Please log in.')
                return redirect(url_for('login'))
    return render_template('auth.html', title='Register', action='register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticate the submitted credentials and save the user's ID in session."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = database().execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user is None or not check_password_hash(user['password_hash'], password):
            flash('Incorrect username or password.')
        else:
            # Start with fresh session data before marking this browser as logged in.
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Welcome back!')
            return redirect(url_for('dashboard'))
    return render_template('auth.html', title='Log in', action='login')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    """Log out by removing all session data, including the authenticated user ID."""
    session.clear()
    flash('You have logged out.')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', 'All')
    if category not in ('All', *CATEGORIES):
        category = 'All'
    sql = 'SELECT id, name, category FROM items WHERE owner_id = ?'
    params = [session['user_id']]
    if search:
        sql += ' AND LOWER(name) LIKE ?'
        params.append(f'%{search.lower()}%')
    if category != 'All':
        sql += ' AND category = ?'
        params.append(category)
    sql += ' ORDER BY id DESC'
    items = database().execute(sql, params).fetchall()
    return render_template('dashboard.html', items=items, search=search,
                           category=category, categories=CATEGORIES)


@app.route('/items', methods=['POST'])
@login_required
def add_item():
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '')
    if not 2 <= len(name) <= 80 or category not in CATEGORIES:
        flash('Enter an item name (2–80 characters) and a valid category.')
    else:
        database().execute('INSERT INTO items (owner_id, name, category) VALUES (?, ?, ?)',
                           (session['user_id'], name, category))
        database().commit()
        flash('Item added.')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
