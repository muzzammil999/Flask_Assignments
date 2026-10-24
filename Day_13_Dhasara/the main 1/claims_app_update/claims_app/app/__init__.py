"""Application factory: builds the Flask app and wires config, database, CSRF and routes."""
import re
from decimal import Decimal

from flask import Flask, g, render_template

from .extensions import csrf, db


def inr(n):
    """Format a number as rupees with Indian grouping (12,34,567.50).
    Why: money is shown in the local convention everywhere; Decimal quantize avoids float errors.
    Links: registered as the `inr` template filter in create_app; imported by services.review_checks for warning text.
    """
    d = Decimal(n or 0).quantize(Decimal("0.01"))
    whole, frac = f"{abs(d):.2f}".split(".")
    if len(whole) > 3:
        whole = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", whole[:-3]) + "," + whole[-3:]
    return f"{'-' if d < 0 else ''}₹{whole}.{frac}"


def create_app(overrides=None):
    """Application factory: build and wire the Flask app.
    Why: a factory lets tests create isolated apps (overrides = in-memory DB) and refuses to start without SECRET_KEY.
    Links: loads config.Config, initialises extensions.db/csrf, installs auth.load_user, registers the three route blueprints, seed CLI commands, template filters, context processor and error handler. Called by run.py, wsgi.py and tests.
    """
    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.config.update(overrides or {})
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set the SECRET_KEY environment variable.")
    db.init_app(app)
    csrf.init_app(app)
    from . import auth, routes_admin, routes_claims, routes_main, seed
    app.before_request(auth.load_user)
    for module in (routes_main, routes_claims, routes_admin):
        app.register_blueprint(module.bp)
    seed.register(app)
    app.add_template_filter(lambda s: str(s or "").replace("_", " ").title(), "label")
    app.add_template_filter(inr, "inr")

    @app.context_processor
    def nav_counts():
        """Inject `queue_count` (unassigned submitted claims) into every template.
        Why: the officer sidebar badge needs it on all pages without each route computing it.
        Links: uses g.user (set by auth.load_user) and services.visible_claims; returns None for non-officers.
        """
        user = getattr(g, "user", None)
        if user is None or user.role != "claims_officer":
            return {"queue_count": None}
        from .models import Claim
        from .services import visible_claims
        return {"queue_count": visible_claims(user).filter(Claim.status == "submitted", Claim.officer_user_id.is_(None)).count()}

    @app.errorhandler(403)
    @app.errorhandler(404)
    def error_page(e):
        """Render error.html for 403/404 with the matching status code.
        Why: consistent friendly errors; the abort() calls in auth.login_required and routes_claims.get_claim land here.
        """
        return render_template("error.html", e=e), e.code
    return app
