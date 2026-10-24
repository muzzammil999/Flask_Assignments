"""Tests for the BRD scenarios: access control, transitions, scope, duplicates, payout, persistence, conflicts."""
from datetime import date
from decimal import Decimal

import pytest

from app import create_app, services as sv
from app.extensions import db
from app.models import Claim, ClaimHistory, Settlement, User
from app.seed import seed

PW = "Chinna@9999"


def make_app(uri="sqlite://"):
    """Build an app on the given database, seed it, and freeze 'today' at 2026-10-17."""
    app = create_app({"SQLALCHEMY_DATABASE_URI": uri, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False, "TESTING": True})
    sv.today = lambda: date(2026, 10, 17)
    with app.app_context():
        db.create_all()
        seed(PW)
    return app


@pytest.fixture()
def app():
    """Fresh in-memory app for each test."""
    return make_app()


def login(app, username):
    """Return a test client logged in as the given demo user."""
    c = app.test_client()
    assert c.post("/login", data={"username": username, "password": PW}).status_code == 302
    return c


def claim(app, cid):
    """Load a claim inside the app context."""
    return db.session.get(Claim, cid)


def good_form(**kw):
    """A valid reimbursement form for policyholder aasha (policy 101, member 201)."""
    d = dict(policy_id=101, member_id=201, hospital_id=3, treatment_type="inpatient", admission_date="2026-10-01",
             discharge_date="2026-10-03", requested_amount="10000", description="Test stay", action="submit")
    d.update(kw)
    return d


def test_login_and_anonymous_redirect(app):
    """Anonymous users go to login; wrong passwords fail with a clear message."""
    c = app.test_client()
    assert c.get("/claims").status_code == 302
    r = c.post("/login", data={"username": "aasha", "password": "bad"})
    assert b"Invalid username or password" in r.data


def test_unauthorized_direct_url_and_forged_post(app):
    """A holder cannot open another holder's claim, and wrong roles cannot POST actions."""
    c = login(app, "aasha")
    assert c.get("/claims/1003").status_code == 403           # belongs to policy 102 (bilal)
    assert c.get("/claims/9999").status_code == 404
    assert c.post("/claims/1007/assign").status_code == 403   # holder is not an officer
    assert c.post("/claims/1009/settle", data={"amount": "1"}).status_code == 403
    assert c.get("/admin").status_code == 403


def test_invalid_transition(app):
    """submitted -> approved is not allowed, even for the assigned officer."""
    with app.app_context():
        officer = User.query.filter_by(username="officer_meera").one()
        c = claim(app, 1004)  # in_review, officer 12
        with pytest.raises(sv.RuleError):
            sv.change_status(db.session.get(Claim, 1007), "approved", officer, "x")
        with pytest.raises(sv.RuleError):
            sv.change_status(db.session.get(Claim, 1002), "in_review", officer, "reopen")  # rejected is terminal
        assert c.status == "in_review"


def test_member_policy_mismatch(app):
    """A member from another policy is rejected server-side and nothing is created."""
    c = login(app, "aasha")
    r = c.post("/claims/new", data=good_form(member_id=203))
    assert r.status_code == 400 and b"not covered by the selected policy" in r.data
    with app.app_context():
        assert Claim.query.count() == 13


def test_hospital_scope(app):
    """A desk cannot use another hospital, a non-network hospital, or a future admission date."""
    c = login(app, "city_hospital")
    base = good_form(policy_id=102, member_id=203, hospital_id=1)
    assert b"own hospital" in c.post("/claims/new", data={**base, "hospital_id": 2}).data
    g = login(app, "green_hospital")
    assert b"not in the cashless network" in g.post("/claims/new", data={**base, "hospital_id": 3}).data
    assert b"cannot be in the future" in c.post("/claims/new", data={**base, "admission_date": "2026-10-20"}).data
    with app.app_context():
        assert Claim.query.count() == 13
    assert c.post("/claims/new", data=base).status_code == 302   # valid cashless works


def test_draft_with_future_date_cannot_be_submitted(app):
    """Case 1013: the draft exists, but submitting it is refused and status stays draft."""
    c = login(app, "city_hospital")
    c.post("/claims/1013/submit")
    with app.app_context():
        assert claim(app, 1013).status == "draft"


def test_duplicate_warning(app):
    """1011 and 1012 warn about each other; the claims are not auto-rejected."""
    with app.app_context():
        assert [d.id for d in sv.duplicates(claim(app, 1012))] == [1011]
        assert claim(app, 1012).status == "submitted"
    c = login(app, "officer_meera")
    assert b"Potential duplicate of claim #1011" in c.get("/claims/1012").data


def test_payout_calculation(app):
    """Payout formula from the BRD, plus the seeded settlements."""
    with app.app_context():
        p1, p3 = claim(app, 1001).policy.plan, claim(app, 1008).policy.plan
        assert sv.compute_payout(Decimal("20000"), p1) == Decimal("16200.00")
        assert sv.compute_payout(Decimal("26000"), p1) == Decimal("21600.00")
        assert sv.compute_payout(Decimal("38000"), p3) == Decimal("32850.00")
        assert sv.compute_payout(Decimal("500"), p1) == Decimal("0.00")  # below deductible
        assert sv.remaining_cover(claim(app, 1001).policy) == Decimal("78400.00")


def test_two_officer_assignment_conflict(app):
    """The second officer cannot overwrite the first officer's assignment."""
    a, b = login(app, "officer_meera"), login(app, "officer_rahul")
    a.post("/claims/1007/assign")
    r = b.post("/claims/1007/assign", follow_redirects=True)
    assert b"already assigned" in r.data
    with app.app_context():
        assert claim(app, 1007).officer_user_id == 12


def test_full_workflow_and_history(app):
    """Holder submits -> officer assigns, asks info, gets response, approves -> admin settles to policyholder."""
    h, o, ad = login(app, "aasha"), login(app, "officer_meera"), login(app, "admin_demo")
    r = h.post("/claims/new", data=good_form(discharge_date="2026-10-02"))
    cid = int(r.headers["Location"].rsplit("/", 1)[1])
    assert o.post(f"/claims/{cid}/approve", data={"eligible_amount": "5", "reason": "x"}, follow_redirects=True).status_code == 200
    with app.app_context():
        assert claim(app, cid).status == "submitted"           # approve before review is refused
    o.post(f"/claims/{cid}/assign"); o.post(f"/claims/{cid}/start")
    o.post(f"/claims/{cid}/more-info", data={"document_type": "discharge_summary", "reason": "Please send"})
    h.post(f"/claims/{cid}/checklist", data={"discharge_summary": "received"})
    h.post(f"/claims/{cid}/respond", data={"note": "Sent it"})
    o.post(f"/claims/{cid}/start")
    assert b"cannot exceed" in o.post(f"/claims/{cid}/approve", data={"eligible_amount": "20000", "reason": "r"}, follow_redirects=True).data
    assert b"written reason" in o.post(f"/claims/{cid}/reject", data={"reason": " "}, follow_redirects=True).data
    o.post(f"/claims/{cid}/approve", data={"eligible_amount": "9000", "reason": "Covered after review"})
    assert b"must equal" in ad.post(f"/claims/{cid}/settle", data={"amount": "1"}, follow_redirects=True).data
    ad.post(f"/claims/{cid}/settle", data={"amount": "6300.00"})
    with app.app_context():
        c = claim(app, cid)
        assert c.status == "paid" and c.settlement.payee_type == "policyholder" and c.settlement.amount == Decimal("6300.00")
        assert [(e.from_status, e.to_status) for e in c.history if e.from_status != e.to_status] == [
            (None, "draft"), ("draft", "submitted"), ("submitted", "in_review"), ("in_review", "more_info"),
            ("more_info", "submitted"), ("submitted", "in_review"), ("in_review", "approved"), ("approved", "paid")]
    assert ad.post(f"/claims/{cid}/settle", data={"amount": "6300.00"}, follow_redirects=True).status_code == 200
    with app.app_context():
        assert Settlement.query.filter_by(claim_id=cid).count() == 1   # no double settlement


def test_filters_and_scope(app):
    """Combined filters work and a hospital desk only ever sees its own cashless claims."""
    o = login(app, "officer_meera")
    assert b"1011" in o.get("/claims?q=Harish&status=more_info&claim_type=reimbursement&hospital_id=5").data
    assert b"No claims match" in o.get("/claims?q=Harish&status=paid").data
    h = login(app, "lotus_hospital")
    body = h.get("/claims?hospital_id=1").data
    assert b"No claims match" in body and h.get("/claims/1001").status_code == 403


def test_reports_are_scoped(app):
    """Holder report counts only the holder's claims; admin sees all non-draft claims."""
    with app.app_context():
        assert sum(r[2] for r in sv.report_rows(sv.visible_claims(db.session.get(User, 1)))) == 2
        assert sum(r[2] for r in sv.report_rows(sv.visible_claims(db.session.get(User, 14)))) == 11


def test_restart_persistence(tmp_path):
    """Data written through one app instance is still there for a second instance (same database file)."""
    uri = f"sqlite:///{tmp_path/'t.db'}"
    a = make_app(uri)
    login(a, "aasha").post("/claims/new", data=good_form())
    b = create_app({"SQLALCHEMY_DATABASE_URI": uri, "SECRET_KEY": "test", "TESTING": True})
    with b.app_context():
        assert Claim.query.count() == 14
