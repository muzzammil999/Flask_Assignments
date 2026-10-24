"""module.py - all the SECURITY code of the claims app, in one place.

app.py imports from this file; this file never imports app.py (so there is no circular import
and it can be tested on its own).

WHAT IS HERE
    1. harden_app(app)        - call ONCE after creating the Flask app. Turns on:
                                  * secure session-cookie settings (HttpOnly, SameSite, Secure)
                                  * automatic logout after SESSION_IDLE_MINUTES of inactivity
                                  * security headers on every response (CSP, anti-clickjacking, ...)
                                  * "no-store" caching for logged-in pages (back button shows nothing)
                                  * refuses to start in production with a weak SECRET_KEY
    2. LoginGuard             - blocks password guessing: 5 wrong tries -> 5 minutes locked
    3. check_new_password()   - the password policy (length, letter + digit, not common,
                                  not your username)
    4. csv_safe()             - stops "CSV injection" in Excel exports
    5. is_safe_redirect()     - stops "open redirect" attacks

SETTINGS (all optional, read from .env)
    APP_ENV=production        - turns on the Secure cookie flag, HSTS and the SECRET_KEY check
    SESSION_IDLE_MINUTES=30   - idle time before the user must log in again
"""
import hmac
import os
import threading
import time
from urllib.parse import urlparse

from flask import request, session

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

WEAK_SECRET_KEYS = ("dev-only-change-me", "change-me-to-a-long-random-text", "")
MIN_SECRET_KEY_LENGTH = 32

# A short list of passwords that are always refused (compared in lower case, without symbols).
COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "12345678", "123456789", "1234567890",
    "qwertyuiop", "qwerty123", "iloveyou", "admin123", "administrator", "welcome1", "welcome123",
    "letmein123", "abc12345", "changeme", "changeme123", "india123", "test1234",
}

# Content-Security-Policy: the browser may load scripts/styles/fonts only from these places.
# The app uses Bootstrap + Google Fonts from CDNs, and a few inline style="" attributes.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def is_production():
    """True when APP_ENV=production is set in the environment (.env)."""
    return os.environ.get("APP_ENV", "").lower() == "production"


# ---------------------------------------------------------------------------
# 1. harden_app
# ---------------------------------------------------------------------------
def harden_app(app):
    """Apply every security setting to the Flask app. Call once, right after Flask(...)."""
    production = is_production()

    # --- SECRET_KEY: it signs the login cookie, so a guessable key lets anyone fake a login.
    key = app.secret_key or ""
    weak = key in WEAK_SECRET_KEYS or len(key) < MIN_SECRET_KEY_LENGTH
    if weak and production:
        raise RuntimeError("SECRET_KEY is missing or too weak. Set a random value of at least "
                           f"{MIN_SECRET_KEY_LENGTH} characters in .env  "
                           "(python -c \"import secrets; print(secrets.token_hex(32))\").")
    if weak:
        print("WARNING: SECRET_KEY is weak. Fine for local testing, NOT for a real deployment.")

    # --- Cookie settings
    idle_minutes = int(os.environ.get("SESSION_IDLE_MINUTES", "30"))
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,       # JavaScript cannot read the cookie
        SESSION_COOKIE_SAMESITE="Lax",      # other sites cannot send it with their forms
        SESSION_COOKIE_SECURE=production,   # only over HTTPS when in production
        SESSION_COOKIE_NAME="claims_session",
        MAX_CONTENT_LENGTH=1024 * 1024,     # refuse request bodies bigger than 1 MB
        WTF_CSRF_TIME_LIMIT=3600,           # a form token is valid for 1 hour
    )
    app.config["SESSION_IDLE_SECONDS"] = idle_minutes * 60

    @app.before_request
    def enforce_idle_timeout():
        """Log the user out if they were inactive for too long; otherwise note 'last seen'."""
        if "uid" not in session:
            return None
        now = int(time.time())
        last_seen = session.get("last_seen", now)
        if now - last_seen > app.config["SESSION_IDLE_SECONDS"]:
            session.clear()                 # app.py's load_user() then sees nobody logged in
        else:
            session["last_seen"] = now
        return None

    @app.after_request
    def add_security_headers(response):
        """Add protective headers to every response."""
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"        # no MIME guessing
        response.headers["X-Frame-Options"] = "DENY"                  # cannot be put in an <iframe>
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if "uid" in session and not request.path.startswith("/static/"):
            # Pages with claim data must not be kept in the browser cache.
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response


# ---------------------------------------------------------------------------
# 2. LoginGuard  (brute-force protection)
# ---------------------------------------------------------------------------
class LoginGuard:
    """Counts wrong passwords per (username, IP address) and locks the pair for a while.

    Kept in memory, which is fine for one server process. With several workers or servers,
    keep these counters in Redis/the database instead.
    """

    def __init__(self, max_failures=5, lock_seconds=300):
        self.max_failures = max_failures
        self.lock_seconds = lock_seconds
        self._failures = {}            # key -> (count, time of first failure in this window)
        self._locked_until = {}        # key -> time when the lock ends
        self._lock = threading.Lock()

    @staticmethod
    def _key(username, ip):
        return (username.strip().lower()[:100], ip or "?")

    def seconds_locked(self, username, ip):
        """Return how many seconds this login is still locked (0 = not locked)."""
        key = self._key(username, ip)
        with self._lock:
            remaining = self._locked_until.get(key, 0) - time.time()
            if remaining <= 0:
                self._locked_until.pop(key, None)
                return 0
            return int(remaining) + 1

    def record_failure(self, username, ip):
        """Count one wrong password; lock the login when the limit is reached."""
        key = self._key(username, ip)
        now = time.time()
        with self._lock:
            count, started = self._failures.get(key, (0, now))
            if now - started > self.lock_seconds:        # old failures expire
                count, started = 0, now
            count += 1
            self._failures[key] = (count, started)
            if count >= self.max_failures:
                self._locked_until[key] = now + self.lock_seconds
                self._failures.pop(key, None)

    def record_success(self, username, ip):
        """Forget the failures after a correct login."""
        with self._lock:
            self._failures.pop(self._key(username, ip), None)

    def reset(self):
        """Forget everything (used by the tests)."""
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()


login_guard = LoginGuard()


def dummy_password_check(check_function):
    """Burn the same time as a real password check when the username does not exist.

    Without this, an attacker could measure response times to learn which usernames exist.
    `check_function` is e.g. werkzeug's check_password_hash.
    """
    check_function("pbkdf2:sha256:600000$x$" + "0" * 64, "not-the-password")


def same_text(a, b):
    """Compare two secret strings in constant time."""
    return hmac.compare_digest(str(a).encode(), str(b).encode())


# ---------------------------------------------------------------------------
# 3. Password policy
# ---------------------------------------------------------------------------
def check_new_password(new_password, username=None):
    """Return an error text if the password breaks the policy, otherwise None.

    Rules (checked in this order):
      * 8 to 128 characters
      * at least one letter and at least one digit
      * not a well-known password (password123, 12345678, ...)
      * does not contain the username
    """
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(new_password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if not any(c.isalpha() for c in new_password) or not any(c.isdigit() for c in new_password):
        return "Password must contain at least one letter and one number."
    simple = "".join(c for c in new_password.lower() if c.isalnum())
    if simple in COMMON_PASSWORDS:
        return "That password is too common. Choose a less guessable one."
    if username and len(username) >= 3 and username.lower() in new_password.lower():
        return "Password must not contain the username."
    return None


# ---------------------------------------------------------------------------
# 4. CSV injection
# ---------------------------------------------------------------------------
def csv_safe(value):
    """Make a value safe for a CSV that will be opened in Excel.

    Excel runs text starting with = + - @ (or a tab / carriage return) as a formula.
    An apostrophe in front turns it back into plain text.
    """
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


# ---------------------------------------------------------------------------
# 5. Open redirect
# ---------------------------------------------------------------------------
def is_safe_redirect(target):
    """True only for a relative path on THIS site (e.g. "/claims"), never "http://evil.com"."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return False
    parts = urlparse(target)
    return not parts.scheme and not parts.netloc
