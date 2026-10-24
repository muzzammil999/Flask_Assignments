"""Login, logout, dashboard, policies and hospital directory pages."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from . import services as sv
from .auth import login_required
from .extensions import db
from .models import Claim, Hospital, Policy, User

bp = Blueprint("main", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Show login form and authenticate on POST.
    Why: one generic error for bad user or password avoids revealing which usernames exist; session.clear() prevents session fixation.
    Links: User.check_password; on success redirects to dashboard; auth.load_user reads the uid it sets.
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
    """Clear the session and go back to login. POST-only so CSRF protection applies.
    """
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/")
@login_required()
def dashboard():
    """Role-specific home page with KPIs, officer counters and 8 newest claims.
    Why: gives each role an at-a-glance workload, always limited to claims they may see.
    Links: services.visible_claims -> services.kpis; OPEN_STATUSES for officer counters.
    """
    q = sv.visible_claims(g.user)
    extra = {}
    if g.user.role == "claims_officer":
        extra = {"Unassigned submitted": q.filter(Claim.status == "submitted", Claim.officer_user_id.is_(None)).count(),
                 "My open claims": q.filter(Claim.officer_user_id == g.user.id, Claim.status.in_(sv.OPEN_STATUSES)).count()}
    recent = q.order_by(Claim.id.desc()).limit(8).all()
    return render_template("dashboard.html", k=sv.kpis(q), extra=extra, recent=recent)


@bp.route("/policies")
@login_required("policyholder")
def policies():
    """Policyholder's own policies with plan benefits, members and remaining cover.
    Links: passes services.remaining_cover to the template; policyholder role only.
    """
    rows = Policy.query.filter_by(holder_user_id=g.user.id).order_by(Policy.id).all()
    return render_template("policies.html", policies=rows, cover=sv.remaining_cover)


@bp.route("/hospitals")
@login_required()
def hospitals():
    """Hospital directory showing cashless network status; visible to every logged-in user.
    """
    return render_template("hospitals.html", hospitals=Hospital.query.order_by(Hospital.name).all())
