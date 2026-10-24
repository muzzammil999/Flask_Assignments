"""Session login helpers and the role guard used by every protected route."""
from functools import wraps

from flask import abort, g, redirect, session, url_for

from .extensions import db
from .models import User


def load_user():
    """Before each request, load the logged-in user (or None) into g.user."""
    g.user = db.session.get(User, session["uid"]) if "uid" in session else None
    if g.user is None:
        session.pop("uid", None)


def login_required(*roles):
    """Route decorator: send anonymous users to login and return 403 for a wrong role.
    With no roles listed, any logged-in user may pass.
    """
    def deco(fn):
        """Wrap the view function with the login and role check."""
        @wraps(fn)
        def inner(*a, **kw):
            """Run the check, then the real view."""
            if g.user is None:
                return redirect(url_for("main.login"))
            if roles and g.user.role not in roles:
                abort(403)
            return fn(*a, **kw)
        return inner
    return deco
