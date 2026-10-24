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
    """Admin screen listing hospitals, plans and users with add/edit forms.
    Why: reference data is maintained in-app; no delete so claims never lose their links.
    Links: posts go to the routes made by save_route; reads ROLES and services.TREATMENTS for form options.
    """
    return render_template("admin.html", hospitals=Hospital.query.order_by(Hospital.id).all(),
                           plans=Plan.query.order_by(Plan.id).all(), users=User.query.order_by(User.id).all(),
                           roles=ROLES, treatments=sv.TREATMENTS)


def save_route(path, fn, message, endpoint):
    """Factory that registers a POST /admin/<path> endpoint for one save function.
    Why: hospital/plan/user saves share the same commit / rollback / flash / redirect pattern, so it is written once.
    Links: called three times below with services.save_hospital/save_plan/save_user; save_user also gets g.user to block self role change.
    """
    @bp.route(f"/admin/{path}", methods=["POST"], endpoint=endpoint)
    @login_required("admin")
    def view():
        """Run the service save, commit, flash result; roll back and flash on RuleError.
        Why: keeps each save atomic and shows rule errors to the admin instead of a 500.
        """
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
    """Reports page: counts and totals by status/type for the user's visible claims.
    Why: scoping through visible_claims means holders and desks never see others' figures.
    Links: services.visible_claims -> services.report_rows; template reports.html.
    """
    rows = sv.report_rows(sv.visible_claims(g.user))
    totals = [sum(r[i] for r in rows) for i in (2, 3, 4, 5)]
    return render_template("reports.html", rows=rows, totals=totals)


@bp.route("/settlements")
@login_required()
def settlements():
    """Settlement ledger page: KPI totals, approved claims awaiting payout, recorded settlements.
    Links: services.visible_claims, kpis, pending_payouts, settlement_rows; admins settle via claims.settle route.
    """
    q = sv.visible_claims(g.user)
    return render_template("settlements.html", k=sv.kpis(q), pending=sv.pending_payouts(q), rows=sv.settlement_rows(q))
