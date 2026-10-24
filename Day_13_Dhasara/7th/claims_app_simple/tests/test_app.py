"""Tests for the simple Claims app: access control, workflow, money rules, per-user passwords.

Run with:  python -m pytest
The tests use a temporary SQLite file, so MySQL is NOT needed and your real data is never touched.
"""
import os
import tempfile
from datetime import date
from decimal import Decimal

# The database address must be chosen BEFORE app.py is imported (app.py reads it at import time).
TEST_DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

import pytest  # noqa: E402

import app as sv  # noqa: E402  (the whole project lives in app.py)
from app import Claim, ClaimHistory, Settlement, User, db, seed  # noqa: E402

sv.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)   # no CSRF token needed in tests

# Every demo user's own password, read from the same CSV file the seed command uses.
PASSWORDS = {row["username"]: row["password"] for row in sv.read_csv("users")}


@pytest.fixture()
def app():
    """Give each test a fresh, seeded database and freeze 'today' at 2026-10-17."""
    sv.today = lambda: date(2026, 10, 17)
    sv.login_guard.reset()          # failed-login counters must not leak between tests
    with sv.app.app_context():
        db.drop_all()
        db.create_all()
        seed()
    return sv.app


def login(app, username, password=None):
    """Return a test browser logged in as the given demo user (using THEIR own password)."""
    c = app.test_client()
    r = c.post("/login", data={"username": username, "password": password or PASSWORDS[username]})
    assert r.status_code == 302
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


def test_restart_persistence(app):
    """Data written is still there after the connection pool is thrown away (like a restart)."""
    login(app, "aasha").post("/claims/new", data=good_form())
    with app.app_context():
        db.session.remove()
        db.engine.dispose()          # close every connection, as if the server stopped
        assert Claim.query.count() == 14


def test_csv_export_is_scoped_and_filtered(app):
    """Holder export has only own claims; filters apply; formula-looking text is neutralised."""
    body = login(app, "aasha").get("/claims/export.csv").data.decode()
    assert body.splitlines()[0].startswith("claim_id,") and "1002" in body and "1003" not in body
    assert "1011" not in login(app, "officer_meera").get("/claims/export.csv?status=paid").data.decode()
    assert sv.csv_safe("=1+1") == "'=1+1" and sv.csv_safe("Asha") == "Asha"


def test_dashboard_kpis_and_ledger(app):
    """KPI numbers come from the database; the ledger lists seeded settlements and only admins can quick-settle."""
    with app.app_context():
        k = sv.kpis(sv.visible_claims(db.session.get(User, 14)))
        assert k["total"] == 11 and k["paid_n"] == 2 and k["paid_amt"] == Decimal("54450.00") and k["settle_n"] == 2
    ad = login(app, "admin_demo")
    page = ad.get("/settlements").data.decode()
    assert "SET-1" in page and "₹54,450.00" in page and "Record settlement" in page
    assert b"Record settlement" not in login(app, "officer_meera").get("/settlements").data
    ad.post("/claims/1003/settle", data={"amount": "14700.00"})           # 16000 eligible on plan 2: (16000-1000)*0.95 = 14250
    with app.app_context():
        assert claim(app, 1003).status == "approved"                        # wrong amount refused
    ad.post("/claims/1003/settle", data={"amount": "14250.00"})
    with app.app_context():
        assert claim(app, 1003).status == "paid" and claim(app, 1003).settlement.payee_type == "hospital"
    assert login(app, "city_hospital").get("/settlements").data.count(b"SET-") <= 3   # only CityCare-linked claims


def test_rupee_format_and_pages(app):
    """Indian digit grouping and every main page renders for every role."""
    from app import inr
    assert inr(1234567.5) == "₹12,34,567.50" and inr(999) == "₹999.00"
    for user in ("aasha", "city_hospital", "officer_meera", "admin_demo"):
        c = login(app, user)
        for path in ("/", "/claims", "/settlements", "/reports", "/hospitals", "/claims/1001" if user != "aasha" else "/claims/1002"):
            assert c.get(path).status_code == 200, (user, path)


# ---------------------------------------------------------------------------
# NEW: every user has their own password, and every user can change it
# ---------------------------------------------------------------------------
def test_every_user_has_a_different_password_and_hash(app):
    """No two demo users share a password, and no two share a stored hash."""
    assert len(set(PASSWORDS.values())) == len(PASSWORDS) == 15
    with app.app_context():
        hashes = [u.password_hash for u in User.query.all()]
        assert len(set(hashes)) == len(hashes)          # also true for equal passwords (salted)
        assert all(len(p) >= sv.MIN_PASSWORD_LENGTH for p in PASSWORDS.values())


def test_one_users_password_does_not_open_another_account(app):
    """aasha's password cannot log in as bilal or as the admin, and the reverse."""
    c = app.test_client()
    for username, other in (("bilal", "aasha"), ("admin_demo", "aasha"), ("aasha", "admin_demo")):
        r = c.post("/login", data={"username": username, "password": PASSWORDS[other]})
        assert b"Invalid username or password" in r.data


def test_change_password_requires_login(app):
    """An anonymous visitor is sent to the login page."""
    c = app.test_client()
    assert c.get("/change-password").status_code == 302
    assert c.post("/change-password", data={}).status_code == 302


def test_change_password_success(app):
    """The new password works, the old one stops working, other users are unaffected."""
    c = login(app, "aasha")
    assert c.get("/change-password").status_code == 200
    r = c.post("/change-password", data={"current_password": PASSWORDS["aasha"],
                                         "new_password": "Brand#New99", "confirm_password": "Brand#New99"})
    assert r.status_code == 302                                   # redirected to the dashboard
    assert c.get("/").status_code == 200                          # still logged in
    fresh = app.test_client()
    assert fresh.post("/login", data={"username": "aasha", "password": PASSWORDS["aasha"]}).status_code == 200  # old: refused
    assert fresh.post("/login", data={"username": "aasha", "password": "Brand#New99"}).status_code == 302      # new: works
    login(app, "bilal")                                           # bilal's password is untouched


@pytest.mark.parametrize("current,new,confirm,message", [
    ("wrong-password", "Brand#New99", "Brand#New99", b"current password is not correct"),
    ("CURRENT", "short", "short", b"at least 8 characters"),
    ("CURRENT", "Brand#New99", "Different#99", b"do not match"),
    ("CURRENT", "CURRENT", "CURRENT", b"must be different"),
    ("CURRENT", "x" * 129, "x" * 129, b"at most 128"),
])
def test_change_password_rejects_bad_input(app, current, new, confirm, message):
    """Each mistake gives a clear message, status 400, and the password stays the same."""
    c = login(app, "aasha")
    same = PASSWORDS["aasha"]
    data = {"current_password": same if current == "CURRENT" else current,
            "new_password": same if new == "CURRENT" else new,
            "confirm_password": same if confirm == "CURRENT" else confirm}
    r = c.post("/change-password", data=data)
    assert r.status_code == 400 and message in r.data
    login(app, "aasha")                                           # the old password still works


def test_admin_can_reset_a_users_password_and_create_users(app):
    """Admin resets bilal's password; a new user needs their own valid password."""
    ad = login(app, "admin_demo")
    ad.post("/admin/user", data={"id": "2", "display_name": "Bilal Khan", "role": "policyholder",
                                 "password": "Reset#Pass1"})
    login(app, "bilal", "Reset#Pass1")
    r = ad.post("/admin/user", data={"username": "newbie", "display_name": "New Person",
                                     "role": "policyholder", "password": "short"}, follow_redirects=True)
    assert b"at least 8 characters" in r.data
    with app.app_context():
        assert User.query.filter_by(username="newbie").first() is None
    ad.post("/admin/user", data={"username": "newbie", "display_name": "New Person",
                                 "role": "policyholder", "password": "Fresh#Pass2026"})
    login(app, "newbie", "Fresh#Pass2026")
    # Leaving the password box empty when editing keeps the old password.
    ad.post("/admin/user", data={"id": "2", "display_name": "Bilal K", "role": "policyholder", "password": ""})
    login(app, "bilal", "Reset#Pass1")


def test_only_admin_can_use_the_admin_user_form(app):
    """A normal user cannot reset anybody's password by posting to the admin form."""
    c = login(app, "aasha")
    assert c.post("/admin/user", data={"id": "2", "role": "policyholder", "password": "Hacked#123"}).status_code == 403
    login(app, "bilal")                                           # bilal's password was not changed


def test_login_page_and_change_password_page_render(app):
    """The new page and the JavaScript hooks are on the page."""
    page = login(app, "aasha").get("/change-password").data
    assert b'id="new_password"' in page and b"data-show-password" in page
    assert b"data-show-password" in app.test_client().get("/login").data


# ---------------------------------------------------------------------------
# NEW: security module (module.py)
# ---------------------------------------------------------------------------
def test_security_headers_and_cookie_flags(app):
    """Every response carries the protective headers; the cookie is HttpOnly + SameSite."""
    r = app.test_client().get("/login")
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Content-Type-Options"] == "nosniff"
    c = login(app, "aasha")
    assert c.get("/").headers["Cache-Control"] == "no-store"      # logged-in pages are never cached
    r = app.test_client().post("/login", data={"username": "aasha", "password": PASSWORDS["aasha"]})
    header = r.headers["Set-Cookie"]
    assert "HttpOnly" in header and "SameSite=Lax" in header


def test_login_is_locked_after_five_wrong_passwords(app):
    """5 wrong passwords lock that username; even the right password is refused (429)."""
    c = app.test_client()
    for _ in range(5):
        assert c.post("/login", data={"username": "bilal", "password": "wrong"}).status_code == 200
    r = c.post("/login", data={"username": "bilal", "password": PASSWORDS["bilal"]})
    assert r.status_code == 429 and b"Too many failed attempts" in r.data
    # another username is not affected
    assert c.post("/login", data={"username": "aasha", "password": PASSWORDS["aasha"]}).status_code == 302


def test_idle_session_expires(app):
    """After the idle limit the user is sent back to the login page."""
    c = login(app, "aasha")
    assert c.get("/").status_code == 200
    with c.session_transaction() as s:
        s["last_seen"] = s["last_seen"] - app.config["SESSION_IDLE_SECONDS"] - 5
    assert c.get("/").status_code == 302


@pytest.mark.parametrize("password,message", [
    ("onlyletters", "letter and one number"),
    ("12345678", "letter and one number"),
    ("Password123", "too common"),
    ("xaasha#2026", "username"),
])
def test_password_policy(password, message):
    """module.check_new_password enforces the extra rules."""
    assert message in sv.module.check_new_password(password, "aasha")
    assert sv.module.check_new_password("Brand#New99", "aasha") is None


def test_safe_redirect_and_csv_helpers():
    """Open-redirect and CSV-injection helpers."""
    m = sv.module
    assert m.is_safe_redirect("/claims") and not m.is_safe_redirect("//evil.com")
    assert not m.is_safe_redirect("https://evil.com") and not m.is_safe_redirect("/\\evil.com")
    assert m.csv_safe("=1+1") == "'=1+1" and m.csv_safe("\t=1") == "'\t=1"


def test_admin_can_give_a_new_user_a_policy_so_the_claim_form_lists_it(app):
    """New policyholder: empty policy list -> admin adds a policy -> it shows on the claim form."""
    ad = login(app, "admin_demo")
    ad.post("/admin/user", data={"username": "newbie", "display_name": "New Person",
                                 "role": "policyholder", "password": "Fresh#Pass2026"})
    with app.app_context():
        uid = User.query.filter_by(username="newbie").first().id
        plan = sv.Plan.query.first().id
    nb = login(app, "newbie", "Fresh#Pass2026")
    assert b"Policy " not in nb.get("/claims/new").data.split(b'id="policy_id"')[1].split(b"</select>")[0]
    bad = ad.post("/admin/policy", data={"holder_user_id": "14", "plan_id": str(plan), "status": "active",
                                         "start_date": "2026-01-01", "end_date": "2026-12-31"},
                  follow_redirects=True)
    assert b"Policyholder role" in bad.data                      # an admin cannot hold a policy
    ad.post("/admin/policy", data={"holder_user_id": str(uid), "plan_id": str(plan), "status": "active",
                                   "start_date": "2026-01-01", "end_date": "2026-12-31"})
    page = nb.get("/claims/new").data
    assert b"New Person (self)" in page and b"Policy 1" in page.split(b'id="policy_id"')[1]
    assert login(app, "aasha").post("/admin/policy", data={}).status_code == 403
