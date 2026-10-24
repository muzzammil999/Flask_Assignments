"""Claim pages: list/queue, create, edit, detail and every workflow action."""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import services as sv
from .auth import login_required
from .extensions import db
from .models import Claim, Hospital, Policy

bp = Blueprint("claims", __name__)
STAFF, SUBMITTERS = ("claims_officer",), ("policyholder", "hospital")


def get_claim(claim_id, lock=False):
    """Load a claim the user may see: 404 if it does not exist, 403 if it belongs to someone else.
    lock=True re-reads the row with FOR UPDATE so two users cannot change it at once.
    """
    if not db.session.get(Claim, claim_id):
        abort(404)
    if not sv.visible_claims(g.user).filter(Claim.id == claim_id).first():
        abort(403)
    return Claim.query.filter_by(id=claim_id).with_for_update().one() if lock else db.session.get(Claim, claim_id)


def act(claim_id, fn, message):
    """Run one workflow action inside a transaction: commit on success, roll back on any error.
    Always redirects back to the claim (post/redirect/get) with a flash message.
    """
    claim = get_claim(claim_id, lock=True)
    try:
        fn(claim, g.user, request.form)
        db.session.commit()
        flash(message, "success")
    except sv.RuleError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("claims.detail", claim_id=claim_id))


def render_list(q, queue):
    """Apply the GET filters to a visible-claims query and render the list page."""
    f = {k: request.args.get(k, "").strip() for k in ("q", "status", "claim_type", "hospital_id")}
    claims = sv.search_claims(q, f["q"], f["status"], f["claim_type"], f["hospital_id"]).order_by(Claim.id).all()
    return render_template("claim_list.html", claims=claims, f=f, queue=queue, today=date.today(),
                           hospitals=Hospital.query.order_by(Hospital.name).all(), statuses=sv.STATUSES)


@bp.route("/claims")
@login_required()
def claim_list():
    """All claims visible to the user, with combined search and filters."""
    return render_list(sv.visible_claims(g.user), queue=False)


@bp.route("/review")
@login_required("claims_officer")
def review_queue():
    """Officer work queue: submitted, in_review and more_info claims with age and assign buttons."""
    return render_list(sv.visible_claims(g.user).filter(Claim.status.in_(sv.OPEN_STATUSES)), queue=True)


def form_page(claim, values, errors):
    """Render the claim form with the user's own policies (holder) or empty IDs (hospital desk)."""
    policies = Policy.query.filter_by(holder_user_id=g.user.id).all() if g.user.role == "policyholder" else []
    return render_template("claim_form.html", claim=claim, v=values, errors=errors, policies=policies,
                           hospitals=Hospital.query.order_by(Hospital.name).all())


def save(claim):
    """Handle a form POST: save as draft or submit; show field errors without saving on failure."""
    submit = request.form.get("action") == "submit"
    try:
        saved = sv.save_claim(g.user, request.form, claim, submit)
        db.session.commit()
    except sv.FormError as e:
        db.session.rollback()
        return form_page(claim, request.form, e.errors), 400
    except sv.RuleError as e:
        db.session.rollback()
        flash(str(e), "danger")
        return form_page(claim, request.form, {}), 400
    flash("Claim submitted." if submit else "Draft saved.", "success")
    return redirect(url_for("claims.detail", claim_id=saved.id))


@bp.route("/claims/new", methods=["GET", "POST"])
@login_required(*SUBMITTERS)
def new_claim():
    """Create a claim: reimbursement for policyholders, cashless for hospital desks."""
    if request.method == "POST":
        return save(None)
    return form_page(None, {"hospital_id": g.user.hospital_id or ""}, {})


@bp.route("/claims/<int:claim_id>/edit", methods=["GET", "POST"])
@login_required(*SUBMITTERS)
def edit_claim(claim_id):
    """Edit your own draft; any other claim or user gets an error."""
    claim = get_claim(claim_id)
    if claim.status != "draft" or claim.created_by_user_id != g.user.id:
        abort(403)
    if request.method == "POST":
        return save(claim)
    return form_page(claim, sv.claim_values(claim), {})


@bp.route("/claims/<int:claim_id>")
@login_required()
def detail(claim_id):
    """Claim detail: policy snapshot, event, checklist, warnings, decision, timeline and allowed actions."""
    claim = get_claim(claim_id)
    staff = g.user.role in ("claims_officer", "admin")
    return render_template("claim_detail.html", claim=claim, actions=sv.available_actions(claim, g.user),
                           docs=sv.checklist(claim), checks=sv.review_checks(claim) if staff else [],
                           info=sv.explain(claim), cover=sv.remaining_cover(claim.policy))


def post_route(path, role, fn, message, endpoint):
    """Register one POST-only workflow action with its role guard and success message."""
    @bp.route(f"/claims/<int:claim_id>/{path}", methods=["POST"], endpoint=endpoint)
    @login_required(*role)
    def view(claim_id):
        """Run the service function for this action through act()."""
        return act(claim_id, fn, message)


post_route("submit", SUBMITTERS, sv.submit_draft, "Claim submitted.", "submit")
post_route("checklist", SUBMITTERS, sv.set_checklist, "Checklist updated.", "checklist")
post_route("respond", SUBMITTERS, sv.respond_more_info, "Response sent; claim is submitted again.", "respond")
post_route("assign", STAFF, sv.assign, "Claim assigned to you.", "assign")
post_route("start", STAFF, sv.start_review, "Review started.", "start")
post_route("more-info", STAFF, sv.request_info, "More information requested.", "more_info")
post_route("approve", STAFF, sv.approve, "Claim approved.", "approve")
post_route("reject", STAFF, sv.reject, "Claim rejected.", "reject")
post_route("settle", ("admin",), sv.settle, "Simulated settlement recorded.", "settle")
