"""Administrator pages (reference data, users) and the reports page for all roles."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from . import services as sv
from .auth import login_required
from .extensions import db
from .models import Hospital, Plan, User, ROLES

bp = Blueprint("admin", __name__)


@bp.route("/admin")
@login_required("admin")
def admin_page():
    """Show hospitals, plans and users with forms to add or edit them (no delete buttons)."""
    return render_template("admin.html", hospitals=Hospital.query.order_by(Hospital.id).all(),
                           plans=Plan.query.order_by(Plan.id).all(), users=User.query.order_by(User.id).all(),
                           roles=ROLES, treatments=sv.TREATMENTS)


def save_route(path, fn, message, endpoint):
    """Register a POST route that saves reference data in one transaction and redirects back."""
    @bp.route(f"/admin/{path}", methods=["POST"], endpoint=endpoint)
    @login_required("admin")
    def view():
        """Call the save function; roll back and flash the error if a rule fails."""
        try:
            fn(request.form, g.user) if fn is sv.save_user else fn(request.form)
            db.session.commit()
            flash(message, "success")
        except sv.RuleError as e:
            db.session.rollback()
            flash(str(e), "danger")
        return redirect(url_for("admin.admin_page"))


save_route("hospital", sv.save_hospital, "Hospital saved.", "save_hospital")
save_route("plan", sv.save_plan, "Plan saved.", "save_plan")
save_route("user", sv.save_user, "User saved.", "save_user")


@bp.route("/reports")
@login_required()
def reports():
    """Counts by status/type plus requested, eligible and simulated paid totals for visible claims only."""
    rows = sv.report_rows(sv.visible_claims(g.user))
    totals = [sum(r[i] for r in rows) for i in (2, 3, 4, 5)]
    return render_template("reports.html", rows=rows, totals=totals)
