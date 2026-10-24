"""Business rules from the BRD. Routes call these; nothing here trusts the browser."""
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import false, func, or_, update

from .extensions import db
from .models import (Claim, ClaimDocument, ClaimHistory, Hospital, Member, Plan,
                     Policy, Settlement, User, ROLES, STATUSES)

DOC_TYPES = ("hospital_bill", "discharge_summary")
TREATMENTS = ("inpatient", "daycare")
OPEN_STATUSES = ("submitted", "in_review", "more_info")
# (from, to) -> who may do it: creator, officer (assigned) or admin
TRANSITIONS = {("draft", "submitted"): "creator", ("submitted", "in_review"): "officer",
               ("in_review", "more_info"): "officer", ("more_info", "submitted"): "creator",
               ("in_review", "approved"): "officer", ("in_review", "rejected"): "officer",
               ("approved", "paid"): "admin"}


class RuleError(Exception):
    """A business rule was broken; the message is safe to show to the user."""


class FormError(Exception):
    """Field-level validation errors stored as {field: message}."""

    def __init__(self, errors):
        """Store the {field: message} dict. Links: raised by save_claim, caught by routes_claims.save to redisplay the form.
        """
        super().__init__("Invalid form")
        self.errors = errors


# ---------- small helpers ----------
def today():
    """Return today's date.
    Why: indirection lets tests monkeypatch the clock. Links: used by validate_claim for the future-date rule.
    """
    return date.today()


def _int(x):
    """Safe text->int (None if invalid). Links: used by _get and search_claims.
    """
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return None


def _get(model, x):
    """Load a row by textual id or None. Why: form ids are untrusted. Links: validate_claim, save_hospital/plan/user.
    """
    i = _int(x)
    return db.session.get(model, i) if i else None


def parse_date(x):
    """Parse YYYY-MM-DD or None. Links: validate_claim.
    """
    try:
        return date.fromisoformat((x or "").strip())
    except ValueError:
        return None


def parse_money(x):
    """Parse text to a 2-place finite Decimal or None (rejects NaN/inf, no floats). Links: validate_claim, approve, settle, save_plan.
    """
    try:
        d = Decimal(str(x).strip())
        return d.quantize(Decimal("0.01")) if d.is_finite() else None
    except (InvalidOperation, AttributeError):
        return None


# ---------- money rules ----------
def compute_payout(eligible, plan):
    """Payout = (eligible - min(eligible, deductible)) x (1 - copay/100), rounded half-up to 2 places.
    Why: the one BRD money formula, Decimal only; e.g. 20000, 2000, 10% -> 16200.00.
    Links: used by explain, pending_payouts and settle (server recomputes; the JS preview is display only).
    """
    eligible = Decimal(eligible)
    net = eligible - min(eligible, plan.deductible)
    return (net * (1 - Decimal(plan.copay_percent) / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def remaining_cover(policy):
    """Annual limit minus settlements already recorded on the policy.
    Why: stops approvals beyond the plan limit. Links: approve, review_checks, routes_claims.detail, routes_main.policies.
    """
    paid = (db.session.query(func.coalesce(func.sum(Settlement.amount), 0))
            .join(Claim, Claim.id == Settlement.claim_id).filter(Claim.policy_id == policy.id).scalar())
    return Decimal(policy.plan.annual_limit) - Decimal(paid)


def explain(claim):
    """Breakdown of requested, eligible, deductible, co-pay and payout (None if not yet assessed).
    Links: uses compute_payout; shown by routes_claims.detail.
    """
    if not claim.eligible_amount:
        return None
    plan, elig = claim.policy.plan, Decimal(claim.eligible_amount)
    payout = compute_payout(elig, plan)
    ded = min(elig, plan.deductible)
    return {"requested": claim.requested_amount, "eligible": elig,
            "reduction": Decimal(claim.requested_amount) - elig, "deductible": ded,
            "copay_pct": plan.copay_percent, "copay": elig - ded - payout, "payout": payout}


# ---------- visibility ----------
def visible_claims(user):
    """Base query of claims the user may see (holder: own policies; hospital: own cashless; staff: non-draft; drafts only to creator).
    Why: the single scoping rule behind lists, reports, KPIs, CSV and get_claim, so data cannot leak by URL.
    Links: nearly every route and the helpers below take its result.
    """
    q = Claim.query
    own_or_open = or_(Claim.status != "draft", Claim.created_by_user_id == user.id)
    if user.role == "policyholder":
        return q.join(Policy, Claim.policy_id == Policy.id).filter(Policy.holder_user_id == user.id, own_or_open)
    if user.role == "hospital":
        if not user.hospital_id:
            return q.filter(false())
        return q.filter(Claim.hospital_id == user.hospital_id, Claim.claim_type == "cashless", own_or_open)
    return q.filter(Claim.status != "draft")


def search_claims(q, text, status, ctype, hospital_id):
    """Add text (id/member name), status, type and hospital filters to a query. Links: routes_claims.filtered.
    """
    if text:
        q = q.join(Member, Claim.member_id == Member.id).filter(or_(
            Claim.id == (int(text) if text.isdigit() else -1), Member.display_name.ilike(f"%{text}%")))
    if status in STATUSES:
        q = q.filter(Claim.status == status)
    if ctype in ("cashless", "reimbursement"):
        q = q.filter(Claim.claim_type == ctype)
    if _int(hospital_id):
        q = q.filter(Claim.hospital_id == _int(hospital_id))
    return q


def status_counts(q):
    """{status: count} for a claims query. Links: kpis and routes_claims.render_list tabs.
    """
    return dict(q.with_entities(Claim.status, func.count(Claim.id)).group_by(Claim.status).all())


def report_rows(q):
    """Grouped rows (status, type, count, requested, eligible, paid) with None->0. Links: routes_admin.reports.
    """
    rows = (q.outerjoin(Settlement, Settlement.claim_id == Claim.id)
            .with_entities(Claim.status, Claim.claim_type, func.count(Claim.id),
                           func.sum(Claim.requested_amount), func.sum(Claim.eligible_amount),
                           func.sum(Settlement.amount))
            .group_by(Claim.status, Claim.claim_type).order_by(Claim.status, Claim.claim_type).all())
    return [[r[0], r[1], r[2]] + [r[i] or Decimal(0) for i in (3, 4, 5)] for r in rows]


def kpis(q):
    """Dashboard/ledger numbers: totals, open work, awaiting settlement, simulated paid.
    Links: status_counts, pending_payouts; used by routes_main.dashboard and routes_admin.settlements.
    """
    counts = status_counts(q)
    open_q = q.filter(Claim.status.in_(OPEN_STATUSES))
    to_settle = pending_payouts(q)
    paid = q.join(Settlement, Settlement.claim_id == Claim.id).with_entities(
        func.coalesce(func.sum(Settlement.amount), 0), func.count(Settlement.id)).one()
    return {"counts": counts, "total": sum(counts.values()),
            "open_n": open_q.count(), "open_amt": open_q.with_entities(func.coalesce(func.sum(Claim.requested_amount), 0)).scalar(),
            "settle_n": len(to_settle), "settle_amt": sum((a for _, a in to_settle), Decimal(0)),
            "paid_amt": paid[0], "paid_n": paid[1]}


def pending_payouts(q):
    """(claim, payout) for approved claims with no settlement. Links: compute_payout; kpis and settlements page.
    """
    return [(c, compute_payout(c.eligible_amount, c.policy.plan))
            for c in q.filter(Claim.status == "approved").order_by(Claim.id).all() if c.settlement is None]


def settlement_rows(q):
    """Settlements of visible claims, newest first. Links: routes_admin.settlements.
    """
    return (Settlement.query.filter(Settlement.claim_id.in_(q.with_entities(Claim.id).statement))
            .order_by(Settlement.recorded_at.desc(), Settlement.id.desc()).all())


def csv_safe(value):
    """Prefix = + - @ with an apostrophe to prevent CSV formula injection. Links: routes_claims.export_csv.
    """
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def checklist(claim):
    """{document type: received/missing}; absent row = missing. Links: review_checks, set_checklist, detail.
    """
    got = {d.document_type: d.checklist_status for d in claim.documents}
    return {t: got.get(t, "missing") for t in DOC_TYPES}


def duplicates(claim):
    """Other claims with same member, hospital, dates and type.
    Why: warning only; officers decide. Links: review_checks.
    """
    return Claim.query.filter(
        Claim.id != claim.id, Claim.member_id == claim.member_id, Claim.hospital_id == claim.hospital_id,
        Claim.admission_date == claim.admission_date, Claim.discharge_date == claim.discharge_date,
        Claim.claim_type == claim.claim_type).all()


def review_checks(claim):
    """Warning list for officers: policy dates/status, treatment cover, duplicates, missing documents, cover left.
    Links: Plan.covers, duplicates, checklist, remaining_cover, inr (local import avoids a circular import); shown by detail for staff.
    """
    p, w = claim.policy, []
    if p.status != "active" or not (p.start_date <= claim.admission_date <= p.end_date):
        w.append(f"Policy {p.id} is not active on the admission date ({p.start_date} to {p.end_date}, {p.status}).")
    if not p.plan.covers(claim.treatment_type):
        w.append(f"Plan '{p.plan.name}' does not cover {claim.treatment_type} treatment.")
    w += [f"Potential duplicate of claim #{d.id} ({d.status})." for d in duplicates(claim)]
    w += [f"Document missing: {t}." for t, s in checklist(claim).items() if s == "missing"]
    from . import inr  # local import avoids a circular import
    w.append(f"Remaining fictional cover on this policy: {inr(remaining_cover(p))}.")
    return w


def next_action(claim):
    """Plain-text next step for a claim status. Why: tells readers who must act. Links: templates.
    """
    return {"draft": "Submitter to submit", "submitted": "Officer to assign/review",
            "in_review": "Officer to decide", "more_info": "Submitter to respond",
            "approved": "Admin to record settlement", "rejected": "Closed", "paid": "Closed"}[claim.status]


def available_actions(claim, user):
    """Set of buttons allowed for this user and claim.
    Why: UI hint only; each action is re-checked in change_status/service functions. Links: routes_claims.detail.
    """
    a, s = set(), claim.status
    if user.role in ("policyholder", "hospital") and claim.created_by_user_id == user.id:
        if s == "draft":
            a |= {"edit", "submit", "checklist"}
        if s == "more_info":
            a |= {"checklist", "respond"}
    if user.role == "claims_officer":
        if s == "submitted" and claim.officer_user_id is None:
            a.add("assign")
        if claim.officer_user_id == user.id:
            if s == "submitted":
                a.add("start")
            if s == "in_review":
                a |= {"more_info", "decide"}
    if user.role == "admin" and s == "approved" and claim.settlement is None:
        a.add("settle")
    return a


# ---------- history and transitions ----------
def log(claim, actor, frm, to, note):
    """Append an audit ClaimHistory row with the next sequence number (flush, no commit).
    Why: audit trail must commit with the change it describes. Links: change_status, save_claim, set_checklist, assign.
    """
    last = db.session.query(func.max(ClaimHistory.sequence_no)).filter(ClaimHistory.claim_id == claim.id).scalar() or 0
    db.session.add(ClaimHistory(claim_id=claim.id, sequence_no=last + 1, from_status=frm, to_status=to,
                                actor_user_id=actor.id, note=note[:500], timestamp=datetime.now()))
    db.session.flush()


def change_status(claim, to, actor, note):
    """Validate the transition and actor against TRANSITIONS, then log and set status.
    Why: the single state machine gate; raises RuleError so nothing partial is saved.
    Links: log; used by save_claim, submit_draft, respond_more_info, start_review, request_info, approve, reject, settle.
    """
    who = TRANSITIONS.get((claim.status, to))
    if who is None:
        raise RuleError(f"A {claim.status} claim cannot move to {to}.")
    ok = {"creator": claim.created_by_user_id == actor.id,
          "officer": actor.role == "claims_officer" and claim.officer_user_id == actor.id,
          "admin": actor.role == "admin"}[who]
    if not ok:
        raise RuleError("You are not allowed to make this change.")
    log(claim, actor, claim.status, to, note)
    claim.status = to


# ---------- claim creation ----------
def validate_claim(user, v, strict):
    """Validate form values and return (errors, clean values).
    Why: server-side truth; claim type derives from role, ownership/member/hospital rules enforced, future admission only blocked when submitting.
    Links: _get, parse_date, parse_money, today; used by save_claim and submit_draft.
    """
    if user.role not in ("policyholder", "hospital"):
        raise RuleError("Your role cannot create claims.")
    e, ctype = {}, ("reimbursement" if user.role == "policyholder" else "cashless")
    policy, member, hosp = _get(Policy, v.get("policy_id")), _get(Member, v.get("member_id")), _get(Hospital, v.get("hospital_id"))
    if policy is None or (ctype == "reimbursement" and policy.holder_user_id != user.id):
        e["policy_id"], policy = "Choose one of your policies." if ctype == "reimbursement" else "Policy not found.", None
    if member is None or policy is None or member.policy_id != policy.id:
        e["member_id"] = "This member is not covered by the selected policy."
    if ctype == "cashless":
        if hosp is None or hosp.id != user.hospital_id:
            e["hospital_id"] = "You can only submit for your own hospital."
        elif not hosp.network_status:
            e["hospital_id"] = "This hospital is not in the cashless network."
    elif hosp is None:
        e["hospital_id"] = "Choose a hospital."
    if v.get("treatment_type") not in TREATMENTS:
        e["treatment_type"] = "Choose inpatient or daycare."
    adm, dis, amt = parse_date(v.get("admission_date")), parse_date(v.get("discharge_date")), parse_money(v.get("requested_amount"))
    if not adm:
        e["admission_date"] = "Enter a valid date."
    elif strict and adm > today():
        e["admission_date"] = "Admission date cannot be in the future."
    if not dis:
        e["discharge_date"] = "Enter a valid date."
    elif adm and dis < adm:
        e["discharge_date"] = "Discharge cannot be before admission."
    if amt is None or amt <= 0:
        e["requested_amount"] = "Enter an amount above 0."
    desc = (v.get("description") or "").strip()
    if not desc or len(desc) > 255:
        e["description"] = "Enter a description (1-255 characters)."
    return e, dict(claim_type=ctype, policy_id=policy and policy.id, member_id=member and member.id,
                   hospital_id=hosp and hosp.id, treatment_type=v.get("treatment_type"), admission_date=adm,
                   discharge_date=dis, requested_amount=amt, description=desc)


def claim_values(claim):
    """Saved claim -> form-style strings. Why: lets a stored draft be re-validated strictly. Links: submit_draft, routes_claims.edit_claim.
    """
    return {k: str(getattr(claim, k)) for k in ("policy_id", "member_id", "hospital_id", "treatment_type",
                                                "admission_date", "discharge_date", "requested_amount", "description")}


def save_claim(user, v, claim=None, submit=False):
    """Create a draft or edit own draft, optionally submit in the same transaction.
    Links: validate_claim, log, change_status, ClaimDocument defaults; called by routes_claims.save.
    """
    e, c = validate_claim(user, v, strict=submit)
    if e:
        raise FormError(e)
    if claim is None:
        claim = Claim(created_by_user_id=user.id, status="draft", created_at=datetime.now(), **c)
        db.session.add(claim)
        db.session.flush()
        log(claim, user, None, "draft", "Draft created")
        db.session.add_all(ClaimDocument(claim_id=claim.id, document_type=t, checklist_status="missing") for t in DOC_TYPES)
    else:
        if claim.status != "draft" or claim.created_by_user_id != user.id:
            raise RuleError("Only your own draft can be edited.")
        for k, x in c.items():
            setattr(claim, k, x)
        log(claim, user, "draft", "draft", "Draft edited")
    if submit:
        change_status(claim, "submitted", user, "Submitted")
    return claim


# ---------- actions used by routes: fn(claim, user, form) ----------
def submit_draft(claim, user, form):
    """Re-validate strictly then submit a saved draft. Links: validate_claim, claim_values, change_status; route 'submit'.
    """
    e, _ = validate_claim(user, claim_values(claim), strict=True)
    if e:
        raise RuleError(" ".join(e.values()))
    change_status(claim, "submitted", user, "Submitted")


def respond_more_info(claim, user, form):
    """Submitter answers a more-info request (note required) and resubmits. Links: change_status; route 'respond'.
    """
    note = (form.get("note") or "").strip()
    if not note:
        raise RuleError("Write a short response.")
    change_status(claim, "submitted", user, "Response: " + note)


def set_checklist(claim, user, form):
    """Update received/missing flags for draft/more_info claims and audit it. Links: checklist, log; route 'checklist'.
    """
    if claim.created_by_user_id != user.id or claim.status not in ("draft", "more_info"):
        raise RuleError("You cannot change this checklist.")
    cur, changes = checklist(claim), []
    for t in DOC_TYPES:
        s = form.get(t)
        if s in ("received", "missing") and s != cur[t]:
            row = next((d for d in claim.documents if d.document_type == t), None)
            if row:
                row.checklist_status = s
            else:
                db.session.add(ClaimDocument(claim_id=claim.id, document_type=t, checklist_status=s))
            changes.append(f"{t}={s}")
    if changes:
        log(claim, user, claim.status, claim.status, "Checklist updated: " + ", ".join(changes))


def assign(claim, user, form):
    """Officer claims an unassigned submitted claim with one conditional UPDATE.
    Why: atomic, so two officers cannot both win (rowcount check). Links: log; route 'assign'.
    """
    if user.role != "claims_officer":
        raise RuleError("Only claims officers can assign claims.")
    res = db.session.execute(update(Claim).where(Claim.id == claim.id, Claim.status == "submitted",
                                                 Claim.officer_user_id.is_(None)).values(officer_user_id=user.id))
    if res.rowcount != 1:
        raise RuleError("This claim is already assigned or no longer submitted.")
    db.session.refresh(claim)
    log(claim, user, "submitted", "submitted", f"Assigned to {user.display_name}")


def start_review(claim, user, form):
    """Move submitted -> in_review for the assigned officer. Links: change_status; route 'start'.
    """
    change_status(claim, "in_review", user, "Review started")


def _reason(form):
    """Require a non-blank 'reason'. Links: request_info, approve, reject.
    """
    r = (form.get("reason") or "").strip()
    if not r:
        raise RuleError("A written reason is required.")
    return r


def request_info(claim, user, form):
    """Officer requests a document: in_review -> more_info and marks it missing. Links: _reason, change_status; route 'more-info'.
    """
    doc, reason = form.get("document_type"), _reason(form)
    if doc not in DOC_TYPES:
        raise RuleError("Choose the requested document.")
    change_status(claim, "more_info", user, f"Requested {doc}: {reason}")
    set_row = next((d for d in claim.documents if d.document_type == doc), None)
    if set_row:
        set_row.checklist_status = "missing"
    else:
        db.session.add(ClaimDocument(claim_id=claim.id, document_type=doc, checklist_status="missing"))


def approve(claim, user, form):
    """Officer approves with eligible amount (0 < eligible <= requested and <= remaining cover).
    Links: _reason, parse_money, remaining_cover, change_status; route 'approve'; settle later uses eligible_amount.
    """
    reason, elig = _reason(form), parse_money(form.get("eligible_amount"))
    if elig is None or elig <= 0:
        raise RuleError("Eligible amount must be above 0.")
    if elig > claim.requested_amount:
        raise RuleError("Eligible amount cannot exceed the requested amount.")
    if elig > remaining_cover(claim.policy):
        raise RuleError("Eligible amount exceeds the remaining fictional cover.")
    change_status(claim, "approved", user, reason)
    claim.eligible_amount, claim.decision_reason = elig, reason


def reject(claim, user, form):
    """Officer rejects with mandatory reason; eligible becomes 0. Links: _reason, change_status; route 'reject'.
    """
    reason = _reason(form)
    change_status(claim, "rejected", user, reason)
    claim.eligible_amount, claim.decision_reason = Decimal("0.00"), reason


def settle(claim, user, form):
    """Admin records the simulated payout once; amount must equal compute_payout.
    Why: prevents typed/forged amounts and double payment; payee by claim type. Links: compute_payout, change_status, Settlement; route 'settle'.
    """
    if claim.status != "approved" or claim.settlement is not None:
        raise RuleError("Only an approved, unsettled claim can be settled.")
    payout = compute_payout(claim.eligible_amount, claim.policy.plan)
    if parse_money(form.get("amount")) != payout:
        raise RuleError(f"Settlement amount must equal the computed payout {payout}.")
    payee = "hospital" if claim.claim_type == "cashless" else "policyholder"
    change_status(claim, "paid", user, f"Simulated payout {payout} to {payee}")
    db.session.add(Settlement(claim_id=claim.id, payee_type=payee, amount=payout,
                              recorded_by_user_id=user.id, recorded_at=datetime.now()))


# ---------- admin reference data ----------
def _text(form, key, label):
    """Required stripped text field or RuleError. Links: save_hospital, save_plan, save_user.
    """
    val = (form.get(key) or "").strip()
    if not val:
        raise RuleError(f"{label} is required.")
    return val


def save_hospital(form):
    """Create/update a hospital (no delete). Links: _get, _text; admin save_route.
    """
    h = Hospital()
    if form.get("id"):
        h = _get(Hospital, form.get("id"))
        if h is None:
            raise RuleError("Hospital not found.")
    h.name, h.city = _text(form, "name", "Name"), _text(form, "city", "City")
    h.network_status = form.get("network_status") == "1"
    db.session.add(h)


def save_plan(form):
    """Create/update a plan after checking amounts, co-pay 0-100 and treatment types. Links: parse_money, _text; admin save_route.
    """
    p = Plan()
    if form.get("id"):
        p = _get(Plan, form.get("id"))
        if p is None:
            raise RuleError("Plan not found.")
    limit, ded, cop = (parse_money(form.get(k)) for k in ("annual_limit", "deductible", "copay_percent"))
    types = [t for t in form.getlist("covered") if t in TREATMENTS]
    if None in (limit, ded, cop) or limit <= 0 or ded < 0 or not 0 <= cop <= 100 or not types:
        raise RuleError("Enter a limit above 0, deductible 0 or more, co-pay 0-100 and one treatment type.")
    p.name, p.annual_limit, p.deductible, p.copay_percent = _text(form, "name", "Name"), limit, ded, cop
    p.covered_treatment_types = "|".join(types)
    db.session.add(p)


def save_user(form, admin):
    """Create user or change role/hospital/password with username, role, hospital, 8-char password rules and no self role change.
    Links: _get, _text, User.set_password; admin save_route (passes g.user).
    """
    u = User()
    if form.get("id"):
        u = _get(User, form.get("id"))
        if u is None:
            raise RuleError("User not found.")
    else:
        u.username = _text(form, "username", "Username")
        if User.query.filter_by(username=u.username).first():
            raise RuleError("Username already exists.")
    role, hosp = form.get("role"), _get(Hospital, form.get("hospital_id"))
    if role not in ROLES or (role == "hospital" and hosp is None):
        raise RuleError("Choose a valid role (hospital desks need a hospital).")
    if u.id == admin.id and role != u.role:
        raise RuleError("You cannot change your own role.")
    u.display_name, u.role = _text(form, "display_name", "Display name"), role
    u.hospital_id = hosp.id if role == "hospital" else None
    pw = form.get("password") or ""
    if pw or not u.id:
        if len(pw) < 8:
            raise RuleError("Password must be at least 8 characters.")
        u.set_password(pw)
    db.session.add(u)
