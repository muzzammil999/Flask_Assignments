"""Session login helpers and the role guard used by every protected route."""
from functools import wraps

from flask import abort, g, redirect, session, url_for

from .extensions import db
from .models import User


def load_user():
    """Resolve the session user into g.user before every request.
    Why: all authorisation depends on a trusted, server-side user object; a stale/deleted uid is dropped from the session.
    Links: registered via app.before_request in create_app; read by login_required, visible_claims callers and every route.
    """
    g.user = db.session.get(User, session["uid"]) if "uid" in session else None
    if g.user is None:
        session.pop("uid", None)


def login_required(*roles):
    """Decorator factory: require login and optionally one of the given roles.
    Why: central, uniform access control so no route forgets the check (anonymous -> login redirect, wrong role -> 403).
    Links: wraps every protected route in routes_main/routes_claims/routes_admin and post_route/save_route; relies on g.user.
    """
    def deco(fn):
        """Take the view function and return the guarded version (inner closure of login_required).
        """
        @wraps(fn)
        def inner(*a, **kw):
            """Run the login/role check, then call the real view.
            Why: this is where the 302/403 decision happens on each request.
            """
            if g.user is None:
                return redirect(url_for("main.login"))
            if roles and g.user.role not in roles:
                abort(403)
            return fn(*a, **kw)
        return inner
    return deco
