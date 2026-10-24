"""Login, logout, dashboard, policies and hospital directory pages."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from . import services as sv
from .auth import login_required
from .extensions import db
from .models import Claim, Hospital, Policy, User

bp = Blueprint("main", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Check username and password; on success start a fresh session.
    The same message is shown for a wrong user or wrong password.
    """
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if u and u.check_password(request.form.get("password", "")):
            session.clear()
            session["uid"] = u.id
            return redirect(url_for("main.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    """Clear the session and return to the login page."""
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/")
@login_required()
def dashboard():
    """Role dashboard: claim counts by status plus officer-queue numbers, all limited to visible claims."""
    q = sv.visible_claims(g.user)
    extra = {}
    if g.user.role == "claims_officer":
        extra = {"Unassigned submitted": q.filter(Claim.status == "submitted", Claim.officer_user_id.is_(None)).count(),
                 "My open claims": q.filter(Claim.officer_user_id == g.user.id, Claim.status.in_(sv.OPEN_STATUSES)).count()}
    return render_template("dashboard.html", counts=sv.status_counts(q), extra=extra)


@bp.route("/policies")
@login_required("policyholder")
def policies():
    """Show the holder's own policies with plan benefits and covered members."""
    rows = Policy.query.filter_by(holder_user_id=g.user.id).order_by(Policy.id).all()
    return render_template("policies.html", policies=rows, cover=sv.remaining_cover)


@bp.route("/hospitals")
@login_required()
def hospitals():
    """Hospital directory showing which hospitals are in the cashless network."""
    return render_template("hospitals.html", hospitals=Hospital.query.order_by(Hospital.name).all())
