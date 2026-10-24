"""Application factory: builds the Flask app and wires config, database, CSRF and routes."""
from flask import Flask, render_template

from .extensions import csrf, db


def create_app(overrides=None):
    """Create the app. Needs SECRET_KEY; `overrides` lets tests swap the database.
    Registers blueprints, error pages, template filters and the CLI commands.
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
    app.add_template_filter(lambda n: "Rs. {:,.2f}".format(n or 0), "inr")

    @app.errorhandler(403)
    @app.errorhandler(404)
    def error_page(e):
        """Show a friendly error page for forbidden and missing pages."""
        return render_template("error.html", e=e), e.code
    return app
