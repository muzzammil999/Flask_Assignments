"""Claim pages: list/queue, create, edit, detail and every workflow action."""
from datetime import date

import csv
import io

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from . import services as sv
from .auth import login_required
from .extensions import db
from .models import Claim, Hospital, Policy

bp = Blueprint("claims", __name__)
STAFF, SUBMITTERS = ("claims_officer",), ("policyholder", "hospital")


def get_claim(claim_id, lock=False):
    """Fetch one claim after existence and visibility checks (404 / 403).
    Why: single gate that stops users opening claims by guessing URLs; lock=True uses SELECT ... FOR UPDATE so concurrent actions serialise.
    Links: uses services.visible_claims; called by act, edit_claim and detail.
    """
    if not db.session.get(Claim, claim_id):
        abort(404)
    if not sv.visible_claims(g.user).filter(Claim.id == claim_id).first():
        abort(403)
    return Claim.query.filter_by(id=claim_id).with_for_update().one() if lock else db.session.get(Claim, claim_id)


def act(claim_id, fn, message):
    """Run one workflow action: lock claim, call service fn, commit or roll back, flash, redirect.
    Why: every state change shares one transactional pattern, so a failed rule never leaves partial data (post/redirect/get).
    Links: invoked by every view built in post_route; fn is a services.* action (fn(claim, user, form)).
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


def filtered(q):
    """Read GET filters (q, status, claim_type, hospital_id) and apply them.
    Why: list page and CSV export must filter identically. Links: services.search_claims; used by render_list and export_csv.
    """
    f = {k: request.args.get(k, "").strip() for k in ("q", "status", "claim_type", "hospital_id")}
    return sv.search_claims(q, f["q"], f["status"], f["claim_type"], f["hospital_id"]).order_by(Claim.id), f


def render_list(q, queue):
    """Render claim_list.html for a visible-claims query.
    Why: /claims and /review differ only by base query and `queue` flag. Links: filtered, services.status_counts; called by claim_list and review_queue.
    """
    q2, f = filtered(q)
    return render_template("claim_list.html", claims=q2.all(), f=f, queue=queue, today=date.today(),
                           counts=sv.status_counts(q), hospitals=Hospital.query.order_by(Hospital.name).all(), statuses=sv.STATUSES)


@bp.route("/claims/export.csv")
@login_required()
def export_csv():
    """Download the filtered, visible claims as CSV.
    Why: reporting outside the app without leaking other users' claims; csv_safe blocks spreadsheet formula injection.
    Links: services.visible_claims, filtered, services.csv_safe.
    """
    q, _ = filtered(sv.visible_claims(g.user))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["claim_id", "member", "policy_id", "hospital", "type", "treatment", "status", "admission", "discharge", "requested", "eligible", "officer"])
    for c in q.all():
        w.writerow([c.id] + [sv.csv_safe(x) for x in (c.member.display_name, c.policy_id, c.hospital.name, c.claim_type, c.treatment_type,
                   c.status, c.admission_date, c.discharge_date, c.requested_amount, c.eligible_amount, c.officer.display_name if c.officer else "")])
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=claims.csv"})


@bp.route("/claims")
@login_required()
def claim_list():
    """List all claims the user may see, with search/filters. Links: render_list(visible_claims).
    """
    return render_list(sv.visible_claims(g.user), queue=False)


@bp.route("/review")
@login_required("claims_officer")
def review_queue():
    """Officer work queue of open (submitted/in_review/more_info) claims. Links: render_list with services.OPEN_STATUSES.
    """
    return render_list(sv.visible_claims(g.user).filter(Claim.status.in_(sv.OPEN_STATUSES)), queue=True)


def form_page(claim, values, errors):
    """Render claim_form.html with values, errors and the user's policy/hospital choices.
    Why: shared by new, edit and failed-save paths. Links: called by new_claim, edit_claim, save.
    """
    policies = Policy.query.filter_by(holder_user_id=g.user.id).all() if g.user.role == "policyholder" else []
    return render_template("claim_form.html", claim=claim, v=values, errors=errors, policies=policies,
                           hospitals=Hospital.query.order_by(Hospital.name).all())


def save(claim):
    """Handle claim form POST: save draft or submit.
    Why: FormError keeps the user's input and shows field errors (400); RuleError flashes; success redirects to detail.
    Links: services.save_claim; called by new_claim and edit_claim.
    """
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
    """Create-claim page; type is fixed by role (holder=reimbursement, desk=cashless). Links: form_page / save(None).
    """
    if request.method == "POST":
        return save(None)
    return form_page(None, {"hospital_id": g.user.hospital_id or ""}, {})


@bp.route("/claims/<int:claim_id>/edit", methods=["GET", "POST"])
@login_required(*SUBMITTERS)
def edit_claim(claim_id):
    """Edit own draft only (403 otherwise). Links: get_claim, services.claim_values, save(claim).
    """
    claim = get_claim(claim_id)
    if claim.status != "draft" or claim.created_by_user_id != g.user.id:
        abort(403)
    if request.method == "POST":
        return save(claim)
    return form_page(claim, sv.claim_values(claim), {})


@bp.route("/claims/<int:claim_id>")
@login_required()
def detail(claim_id):
    """Claim detail page: data, checklist, staff warnings, payout explanation, timeline and allowed buttons.
    Links: services.available_actions, checklist, review_checks (staff only), explain, remaining_cover; buttons post to post_route endpoints.
    """
    claim = get_claim(claim_id)
    staff = g.user.role in ("claims_officer", "admin")
    return render_template("claim_detail.html", claim=claim, actions=sv.available_actions(claim, g.user),
                           docs=sv.checklist(claim), checks=sv.review_checks(claim) if staff else [],
                           info=sv.explain(claim), cover=sv.remaining_cover(claim.policy))


def post_route(path, role, fn, message, endpoint):
    """Factory that registers a POST-only workflow endpoint with role guard.
    Why: nine actions share one shape, so adding a step is one line. Links: login_required, act, services action functions.
    """
    @bp.route(f"/claims/<int:claim_id>/{path}", methods=["POST"], endpoint=endpoint)
    @login_required(*role)
    def view(claim_id):
        """Delegate to act() with this action's service function and success message.
        """
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
