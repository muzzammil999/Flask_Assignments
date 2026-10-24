"""Health Insurance Claims Simulator - the SIMPLE version (Flask + MySQL, one Python file).

This is a beginner-friendly rewrite of the claims app. It uses the SAME database
(schema.sql, same tables and columns) and the same pages, but the code is plain:
every page and every button has its own small function, and every function has a
docstring that explains what it does.

WHAT THE APP DOES
    * Policyholders and hospital desks create insurance claims.
    * Claims officers review claims and approve or reject them.
    * An administrator records a (simulated) payment for approved claims.
    * Every status change is saved in a history table (an audit trail).
    * Every user has their OWN password, and every user can change it.

HOW TO RUN IT
    1. pip install -r requirements.txt
    2. Copy .env.example to .env and fill in your MySQL details.
    3. flask --app app init-db        (creates the tables)
    4. flask --app app seed           (loads demo data + one password per user)
    5. python app.py                  (open http://127.0.0.1:5000)

HOW TO READ THIS FILE (top to bottom, each part builds on the one before)
    1. Setup              - Flask app, database, security settings
    2. Constants          - roles, statuses and the "who may change what" table
    3. Models             - Python classes that match the database tables
    4. Small helpers      - turning text into numbers/dates, formatting money
    5. Password helpers   - the rules for passwords and for changing them
    6. Login helpers      - who is logged in, and the role check on every page
    7. Business rules     - payout maths, who can see which claim, status changes
    8. Pages (routes)     - one function per web page or button
    9. Demo data + CLI    - `flask init-db` and `flask seed`
    10. Start the server  - python app.py

THE FLOW OF ONE REQUEST (example: an officer clicks "Approve")
    browser -> route function approve_claim()
            -> login_required() checks: logged in? right role?
            -> run_action() loads the claim and calls approve()
            -> approve() checks the rules and calls change_status()
            -> change_status() checks the TRANSITIONS table, saves a history row
            -> the route commits to the database and redirects back to the claim page
"""
import csv
import io
import os
import re
import time
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import wraps
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import false, func, or_, update
from sqlalchemy.engine import URL
from werkzeug.security import check_password_hash, generate_password_hash

import module            # our own security code (see module.py)
from module import csv_safe, login_guard


# =====================================================================
# 1. SETUP
# =====================================================================
load_dotenv()    # copy the values from the .env file into os.environ (see .env.example)

app = Flask(__name__)    # the web application; templates/ and static/ sit next to this file

# SECRET_KEY signs the login cookie so nobody can fake it. Set a long random value in .env.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
if app.secret_key == "dev-only-change-me":
    print("WARNING: set SECRET_KEY in the .env file before sharing this site.")


def get_database_url():
    """Build the database address that SQLAlchemy needs.

    If DATABASE_URL is set (the tests use a sqlite one) it is used as it is.
    Otherwise a MySQL address is built from DB_USER, DB_PASSWORD, DB_HOST and DB_NAME,
    which come from the .env file. URL.create() safely handles special characters
    (like @ or #) inside the password.
    """
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return URL.create(
        "mysql+pymysql",
        username=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "claims_db"))


app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url()
app.config["SESSION_COOKIE_HTTPONLY"] = True    # JavaScript cannot read the login cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"   # other websites cannot send it with their forms

db = SQLAlchemy(app)     # `db` is how we talk to the database
CSRFProtect(app)         # every POST form must carry a hidden token ({{ csrf() }} in templates)
module.harden_app(app)   # cookie flags, security headers, idle timeout, SECRET_KEY check (module.py)

DATA_DIR = Path(__file__).resolve().parent / "data"   # folder with the demo CSV files


# =====================================================================
# 2. CONSTANTS
# =====================================================================
ROLES = ("policyholder", "hospital", "claims_officer", "admin")
STATUSES = ("draft", "submitted", "in_review", "more_info", "approved", "rejected", "paid")
OPEN_STATUSES = ("submitted", "in_review", "more_info")   # claims that still need work
DOC_TYPES = ("hospital_bill", "discharge_summary")        # documents on the checklist
TREATMENTS = ("inpatient", "daycare")

SUBMITTERS = ("policyholder", "hospital")   # roles that may create claims
STAFF = ("claims_officer",)                 # roles that may review claims

MIN_PASSWORD_LENGTH = module.MIN_PASSWORD_LENGTH    # password length limits live in module.py
MAX_PASSWORD_LENGTH = module.MAX_PASSWORD_LENGTH

# THE most important table of the app: which status changes are legal, and WHO may make them.
#   (from_status, to_status): who
#   "creator" = the user who created the claim
#   "officer" = the claims officer the claim is assigned to
#   "admin"   = an administrator
# A change that is not listed here (for example submitted -> approved) is always refused.
TRANSITIONS = {
    ("draft", "submitted"): "creator",
    ("submitted", "in_review"): "officer",
    ("in_review", "more_info"): "officer",
    ("more_info", "submitted"): "creator",
    ("in_review", "approved"): "officer",
    ("in_review", "rejected"): "officer",
    ("approved", "paid"): "admin",
}


# =====================================================================
# 3. MODELS  (one class = one database table, one attribute = one column)
# =====================================================================
# Reading tip: `Hospital.query.filter_by(id=1).first()` means
# "SELECT * FROM hospitals WHERE id = 1 LIMIT 1" and gives back a Hospital object.
class Hospital(db.Model):
    """A hospital. network_status=True means cashless claims are allowed there."""
    __tablename__ = "hospitals"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    network_status = db.Column(db.Boolean, nullable=False, default=False)


class User(db.Model):
    """A person who can log in. Each user has ONE role and their OWN password hash."""
    __tablename__ = "users"
    __table_args__ = (db.CheckConstraint(
        "role in ('policyholder','hospital','claims_officer','admin')", name="ck_user_role"),)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)   # a scrambled password, never the real one
    display_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"))   # only for hospital-desk users
    hospital = db.relationship("Hospital")

    def set_password(self, raw_password):
        """Save a salted hash of the password. The real password is never stored.

        "Salted" means a random value is mixed in, so two users with the same password
        still get different hashes.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Return True if raw_password matches the stored hash, otherwise False."""
        return check_password_hash(self.password_hash, raw_password)


class Plan(db.Model):
    """An insurance plan: yearly limit, deductible, co-pay and covered treatment types."""
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    covered_treatment_types = db.Column(db.String(100), nullable=False)   # saved like "inpatient|daycare"
    annual_limit = db.Column(db.Numeric(12, 2), nullable=False)    # the most the insurer pays per year
    deductible = db.Column(db.Numeric(12, 2), nullable=False)      # the holder pays this first
    copay_percent = db.Column(db.Numeric(5, 2), nullable=False)    # % of the rest the holder pays

    def covers(self, treatment):
        """Return True if this plan covers the given treatment type."""
        return treatment in self.covered_treatment_types.split("|")


class Policy(db.Model):
    """One holder, one plan, a start date, an end date and a status (active / expired)."""
    __tablename__ = "policies"
    id = db.Column(db.Integer, primary_key=True)
    holder_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    holder = db.relationship("User")
    plan = db.relationship("Plan")
    members = db.relationship("Member", backref="policy")


class Member(db.Model):
    """A person covered by exactly one policy."""
    __tablename__ = "members"
    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    relationship = db.Column(db.String(30), nullable=False)



class Claim(db.Model):
    """A request for money: cashless (from a hospital) or reimbursement (from a holder)."""
    __tablename__ = "claims"
    __table_args__ = (
        db.Index("ix_claims_policy_status", "policy_id", "status"),
        db.Index("ix_claims_officer_status", "officer_user_id", "status"),
        db.CheckConstraint("requested_amount > 0", name="ck_claim_amount"),
        db.CheckConstraint("status in ('draft','submitted','in_review','more_info',"
                           "'approved','rejected','paid')", name="ck_claim_status"))
    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False)
    claim_type = db.Column(db.String(20), nullable=False)       # "cashless" or "reimbursement"
    treatment_type = db.Column(db.String(20), nullable=False)   # "inpatient" or "daycare"
    admission_date = db.Column(db.Date, nullable=False)
    discharge_date = db.Column(db.Date, nullable=False)
    requested_amount = db.Column(db.Numeric(12, 2), nullable=False)   # what the submitter asks for
    eligible_amount = db.Column(db.Numeric(12, 2))                    # what the officer accepts
    description = db.Column(db.String(255), nullable=False, default="")
    decision_reason = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="draft")
    officer_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))   # empty until an officer takes it
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    policy = db.relationship("Policy", backref="claims")
    member = db.relationship("Member")
    hospital = db.relationship("Hospital")
    officer = db.relationship("User", foreign_keys=[officer_user_id])
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    documents = db.relationship("ClaimDocument", backref="claim")
    history = db.relationship("ClaimHistory", backref="claim", order_by="ClaimHistory.sequence_no")
    settlement = db.relationship("Settlement", backref="claim", uselist=False)   # at most one


class ClaimDocument(db.Model):
    """Checklist only (no file upload): each document type is 'received' or 'missing'."""
    __tablename__ = "claim_documents"
    __table_args__ = (db.UniqueConstraint("claim_id", "document_type"),)
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False)
    document_type = db.Column(db.String(30), nullable=False)
    checklist_status = db.Column(db.String(20), nullable=False)


class ClaimHistory(db.Model):
    """One audit event: who moved a claim from one status to another, when, and why."""
    __tablename__ = "claim_history"
    __table_args__ = (db.Index("ix_history_claim_time", "claim_id", "timestamp"),
                      db.UniqueConstraint("claim_id", "sequence_no"))
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False)
    sequence_no = db.Column(db.Integer, nullable=False)    # 1, 2, 3 ... for each claim
    from_status = db.Column(db.String(20))                 # empty for the very first event
    to_status = db.Column(db.String(20), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    note = db.Column(db.String(500), nullable=False, default="")
    timestamp = db.Column(db.DateTime, nullable=False)
    actor = db.relationship("User")


class Settlement(db.Model):
    """The simulated payment of an approved claim. A claim can be settled only once."""
    __tablename__ = "settlements"
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), unique=True, nullable=False)
    payee_type = db.Column(db.String(20), nullable=False)     # "hospital" or "policyholder"
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False)
    recorded_by = db.relationship("User")


# =====================================================================
# 4. SMALL HELPERS
# =====================================================================
class RuleError(Exception):
    """Raised when a business rule is broken. The message is safe to show to the user.

    Example: raise RuleError("A written reason is required.")
    The route functions catch it, undo the database changes and flash the message.
    """


def today():
    """Return today's date. It is a function so the tests can pretend it is another day."""
    return date.today()


def to_int(text):
    """Convert text like "12" to the number 12. Return None if it is not a whole number."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def find_by_id(model, text):
    """Load one row by its id, where the id arrives as text from a form.

    Example: find_by_id(Hospital, "3") -> the Hospital with id 3.
    Returns None when the text is empty, not a number, or no such row exists.
    """
    number = to_int(text)
    if not number:
        return None
    return db.session.get(model, number)


def parse_date(text):
    """Convert "2026-10-17" to a date. Return None if the text is not a valid date."""
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def parse_money(text):
    """Convert text like "1500.5" to a Decimal with 2 places (1500.50). None if invalid.

    Money always uses Decimal, never float, because floats make tiny rounding mistakes
    (0.1 + 0.2 = 0.30000000000000004).
    """
    try:
        amount = Decimal(str(text).strip())
    except (InvalidOperation, AttributeError):
        return None
    if not amount.is_finite():          # reject "NaN" and "Infinity"
        return None
    return amount.quantize(Decimal("0.01"))


def inr(number):
    """Format a number as rupees with Indian digit grouping: 1234567.5 -> ₹12,34,567.50.

    Indian grouping puts the last 3 digits together and then groups of 2.
    This function is also available in templates as the filter  {{ value|inr }}.
    """
    amount = Decimal(number or 0).quantize(Decimal("0.01"))
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        front, last_three = whole[:-3], whole[-3:]
        front = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", front)    # comma before every pair of digits
        whole = front + "," + last_three
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{whole}.{fraction}"


def label(text):
    """Make a stored value readable: "more_info" -> "More Info". Template filter {{ x|label }}."""
    return str(text or "").replace("_", " ").title()


# Make the two formatting helpers available inside every template.
app.add_template_filter(inr, "inr")
app.add_template_filter(label, "label")


# =====================================================================
# 5. PASSWORD HELPERS  (rules are in module.py; each user has their own password; users can change it)
# =====================================================================
def check_new_password(new_password, username=None):
    """Password policy lives in module.py (length, letter + digit, not common, not the username)."""
    return module.check_new_password(new_password, username)


def check_password_change(user, current_password, new_password, confirm_password):
    """Check everything on the "Change password" form. Return an error text, or None if all is OK.

    The checks run in this order, and the first problem found is returned:
      1. the current password must be right (proves it is really the owner)
      2. the new password must be different from the current one
      3. the new password must follow the password policy (module.py)
      4. the confirmation must match the new password (catches typing mistakes)
    """
    if not user.check_password(current_password):
        return "Your current password is not correct."
    if new_password == current_password:
        return "The new password must be different from the current password."
    policy_problem = check_new_password(new_password, user.username)
    if policy_problem:
        return policy_problem
    if new_password != confirm_password:
        return "New password and confirmation do not match."
    return None


# =====================================================================
# 6. LOGIN HELPERS
# =====================================================================
@app.before_request
def load_user():
    """Runs automatically before EVERY request: find out who is logged in.

    The login cookie (session) only stores the user's id. Here we load the full
    User from the database into `g.user` ("g" lives for one request only), so every
    page can use g.user. If nobody is logged in, g.user is None.
    """
    g.user = None
    if "uid" in session:
        g.user = db.session.get(User, session["uid"])
        if g.user is None:               # the user was deleted: forget the old cookie value
            session.pop("uid", None)


def login_required(*roles):
    """Decorator that protects a page. Put it directly above a route function.

    Examples:
        @login_required()                      any logged-in user may open the page
        @login_required("admin")               only administrators
        @login_required("policyholder", "hospital")   either of these two roles

    What happens when the page is opened:
        not logged in   -> redirect to the login page
        wrong role      -> error 403 (Forbidden)
        everything OK   -> the page function runs normally
    """
    def decorator(page_function):
        @wraps(page_function)     # keeps the original function's name (Flask needs it)
        def checked_page(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login"))
            if roles and g.user.role not in roles:
                abort(403)
            return page_function(*args, **kwargs)
        return checked_page
    return decorator


# =====================================================================
# 7. BUSINESS RULES  (nothing here trusts the browser; everything is re-checked)
# =====================================================================
# ---------- money ----------
def compute_payout(eligible, plan):
    """Work out how much the insurer pays for an eligible amount.

    Steps:
      1. The holder pays the deductible first:        net = eligible - min(eligible, deductible)
      2. The holder also pays the co-pay % of the rest: payout = net x (1 - copay% / 100)
      3. Round to 2 decimals (half up).

    Example: eligible 20000, deductible 2000, co-pay 10%
             net = 18000, payout = 18000 x 0.90 = 16200.00
    """
    eligible = Decimal(eligible)
    net = eligible - min(eligible, plan.deductible)
    payout = net * (1 - Decimal(plan.copay_percent) / 100)
    return payout.quantize(Decimal("0.01"), ROUND_HALF_UP)


def remaining_cover(policy):
    """Return how much of the policy's yearly limit is still unused.

    = plan annual limit - the sum of all settlements already paid on this policy's claims.
    """
    paid = (db.session.query(func.coalesce(func.sum(Settlement.amount), 0))
            .join(Claim, Claim.id == Settlement.claim_id)
            .filter(Claim.policy_id == policy.id)
            .scalar())
    return Decimal(policy.plan.annual_limit) - Decimal(paid)


def explain(claim):
    """Break an approved/rejected claim's money into parts for the claim page.

    Returns a dict (requested, eligible, reduction, deductible, copay_pct, copay, payout),
    or None when the officer has not entered an eligible amount yet.
    """
    if not claim.eligible_amount:
        return None
    plan = claim.policy.plan
    eligible = Decimal(claim.eligible_amount)
    payout = compute_payout(eligible, plan)
    deductible = min(eligible, plan.deductible)
    return {
        "requested": claim.requested_amount,
        "eligible": eligible,
        "reduction": Decimal(claim.requested_amount) - eligible,   # amount the officer cut
        "deductible": deductible,
        "copay_pct": plan.copay_percent,
        "copay": eligible - deductible - payout,                   # the co-pay in rupees
        "payout": payout,
    }


# ---------- who may see which claim ----------
def visible_claims(user):
    """Return a database query of ONLY the claims this user is allowed to see.

    This is the heart of the access control. Every page that shows claims starts
    from this query, so a user can never reach data that is not theirs.
        policyholder   -> claims on their own policies
        hospital desk  -> cashless claims of their own hospital
        officer/admin  -> all claims
    A draft is visible only to the person who created it.
    """
    query = Claim.query
    not_someone_elses_draft = or_(Claim.status != "draft", Claim.created_by_user_id == user.id)

    if user.role == "policyholder":
        return (query.join(Policy, Claim.policy_id == Policy.id)
                .filter(Policy.holder_user_id == user.id, not_someone_elses_draft))

    if user.role == "hospital":
        if not user.hospital_id:
            return query.filter(false())      # a desk user with no hospital sees nothing
        return query.filter(Claim.hospital_id == user.hospital_id,
                            Claim.claim_type == "cashless",
                            not_someone_elses_draft)

    return query.filter(Claim.status != "draft")    # officers and admins: everything except drafts


def search_claims(query, text, status, claim_type, hospital_id):
    """Narrow a claims query using the filters from the claim list page.

    Every filter is optional; the ones that are empty are ignored.
        text        - a claim id (digits) or part of a member's name
        status      - one of STATUSES
        claim_type  - "cashless" or "reimbursement"
        hospital_id - a hospital id as text
    """
    if text:
        claim_id = int(text) if text.isdigit() else -1      # -1 never matches any claim
        query = (query.join(Member, Claim.member_id == Member.id)
                 .filter(or_(Claim.id == claim_id, Member.display_name.ilike(f"%{text}%"))))
    if status in STATUSES:
        query = query.filter(Claim.status == status)
    if claim_type in ("cashless", "reimbursement"):
        query = query.filter(Claim.claim_type == claim_type)
    if to_int(hospital_id):
        query = query.filter(Claim.hospital_id == to_int(hospital_id))
    return query


# ---------- numbers for the dashboard and reports ----------
def status_counts(query):
    """Count claims per status. Returns a dict like {"submitted": 3, "paid": 2}."""
    rows = query.with_entities(Claim.status, func.count(Claim.id)).group_by(Claim.status).all()
    return dict(rows)


def pending_payouts(query):
    """List approved claims that are still waiting for a settlement.

    Returns a list of (claim, payout_amount) pairs.
    """
    result = []
    approved = query.filter(Claim.status == "approved").order_by(Claim.id).all()
    for claim in approved:
        if claim.settlement is None:
            result.append((claim, compute_payout(claim.eligible_amount, claim.policy.plan)))
    return result


def kpis(query):
    """Calculate the dashboard numbers for a set of claims (a "KPI" is a key number).

    Returns a dict with: counts per status, total claims, open claims (count + amount),
    approved claims waiting for settlement (count + amount), and the simulated amount
    already paid (count + amount).
    """
    counts = status_counts(query)

    open_claims = query.filter(Claim.status.in_(OPEN_STATUSES))
    open_amount = open_claims.with_entities(
        func.coalesce(func.sum(Claim.requested_amount), 0)).scalar()

    waiting = pending_payouts(query)
    waiting_amount = sum((payout for _, payout in waiting), Decimal(0))

    paid_amount, paid_count = (query.join(Settlement, Settlement.claim_id == Claim.id)
                               .with_entities(func.coalesce(func.sum(Settlement.amount), 0),
                                              func.count(Settlement.id)).one())
    return {"counts": counts, "total": sum(counts.values()),
            "open_n": open_claims.count(), "open_amt": open_amount,
            "settle_n": len(waiting), "settle_amt": waiting_amount,
            "paid_amt": paid_amount, "paid_n": paid_count}


def report_rows(query):
    """Build the table of the Reports page.

    One row per (status, claim type): [status, type, how many, total requested,
    total eligible, total paid]. Missing totals become 0.
    """
    rows = (query.outerjoin(Settlement, Settlement.claim_id == Claim.id)
            .with_entities(Claim.status, Claim.claim_type, func.count(Claim.id),
                           func.sum(Claim.requested_amount), func.sum(Claim.eligible_amount),
                           func.sum(Settlement.amount))
            .group_by(Claim.status, Claim.claim_type)
            .order_by(Claim.status, Claim.claim_type).all())
    table = []
    for status, claim_type, count, requested, eligible, paid in rows:
        table.append([status, claim_type, count,
                      requested or Decimal(0), eligible or Decimal(0), paid or Decimal(0)])
    return table


def settlement_rows(query):
    """Return the recorded settlements that belong to the given claims, newest first."""
    claim_ids = query.with_entities(Claim.id).statement
    return (Settlement.query.filter(Settlement.claim_id.in_(claim_ids))
            .order_by(Settlement.recorded_at.desc(), Settlement.id.desc()).all())


# ---------- helpers for the claim detail page ----------
def checklist(claim):
    """Return {document_type: "received" or "missing"} for every document type.

    A document with no row in the database counts as "missing".
    """
    saved = {d.document_type: d.checklist_status for d in claim.documents}
    return {doc_type: saved.get(doc_type, "missing") for doc_type in DOC_TYPES}


def duplicates(claim):
    """Find OTHER claims with the same member, hospital, dates and claim type.

    Only used to warn the officer. A possible duplicate is never rejected automatically.
    """
    return Claim.query.filter(
        Claim.id != claim.id,
        Claim.member_id == claim.member_id,
        Claim.hospital_id == claim.hospital_id,
        Claim.admission_date == claim.admission_date,
        Claim.discharge_date == claim.discharge_date,
        Claim.claim_type == claim.claim_type).all()


def review_checks(claim):
    """Return a list of warning sentences for the officer to read before deciding.

    Warnings only - the officer makes the decision:
      * policy not active on the admission date
      * treatment not covered by the plan
      * possible duplicate claims
      * missing documents
      * how much cover is left on the policy
    """
    policy = claim.policy
    warnings = []
    active_on_admission = (policy.status == "active"
                           and policy.start_date <= claim.admission_date <= policy.end_date)
    if not active_on_admission:
        warnings.append(f"Policy {policy.id} is not active on the admission date "
                        f"({policy.start_date} to {policy.end_date}, {policy.status}).")
    if not policy.plan.covers(claim.treatment_type):
        warnings.append(f"Plan '{policy.plan.name}' does not cover {claim.treatment_type} treatment.")
    for other in duplicates(claim):
        warnings.append(f"Potential duplicate of claim #{other.id} ({other.status}).")
    for doc_type, doc_status in checklist(claim).items():
        if doc_status == "missing":
            warnings.append(f"Document missing: {doc_type}.")
    warnings.append(f"Remaining fictional cover on this policy: {inr(remaining_cover(policy))}.")
    return warnings


def next_action(claim):
    """Return a short sentence saying what must happen next for the claim's status."""
    return {"draft": "Submitter to submit", "submitted": "Officer to assign/review",
            "in_review": "Officer to decide", "more_info": "Submitter to respond",
            "approved": "Admin to record settlement", "rejected": "Closed",
            "paid": "Closed"}[claim.status]


def available_actions(claim, user):
    """Decide which buttons the claim page should show to this user.

    Returns a set of names such as {"edit", "submit", "assign", "approve"...}.
    This only controls what is SHOWN. Every button is checked again on the server
    when it is clicked, so hiding a button is not the security.
    """
    actions = set()
    status = claim.status

    # The creator (holder or hospital desk) can work on their own draft / more_info claim.
    if user.role in SUBMITTERS and claim.created_by_user_id == user.id:
        if status == "draft":
            actions |= {"edit", "submit", "checklist"}
        if status == "more_info":
            actions |= {"checklist", "respond"}

    # Claims officers: take an unassigned claim, or work on the claim assigned to them.
    if user.role == "claims_officer":
        if status == "submitted" and claim.officer_user_id is None:
            actions.add("assign")
        if claim.officer_user_id == user.id:
            if status == "submitted":
                actions.add("start")
            if status == "in_review":
                actions |= {"more_info", "decide"}

    # Admins record the payment once for an approved claim.
    if user.role == "admin" and status == "approved" and claim.settlement is None:
        actions.add("settle")
    return actions


# ---------- history and status changes ----------
def log_history(claim, actor, from_status, to_status, note):
    """Add one audit row to the claim's history (saved with the next database commit).

    The sequence number is "last number + 1" so the timeline stays in order.
    """
    last_number = (db.session.query(func.max(ClaimHistory.sequence_no))
                   .filter(ClaimHistory.claim_id == claim.id).scalar()) or 0
    db.session.add(ClaimHistory(
        claim_id=claim.id, sequence_no=last_number + 1,
        from_status=from_status, to_status=to_status,
        actor_user_id=actor.id, note=note[:500], timestamp=datetime.now()))
    db.session.flush()     # send it to the database now (still inside the transaction)


def change_status(claim, new_status, actor, note):
    """Move a claim to a new status. THIS IS THE ONLY PLACE where a status may change.

    Steps:
      1. Look up (current status, new status) in TRANSITIONS. Not found -> RuleError.
      2. Check the actor is the person that transition needs (creator / officer / admin).
         Wrong person -> RuleError.
      3. Write the history row and set the new status.
    Because a RuleError stops the function before step 3, nothing half-done is saved.
    """
    who_may_do_it = TRANSITIONS.get((claim.status, new_status))
    if who_may_do_it is None:
        raise RuleError(f"A {claim.status} claim cannot move to {new_status}.")

    if who_may_do_it == "creator":
        allowed = claim.created_by_user_id == actor.id
    elif who_may_do_it == "officer":
        allowed = actor.role == "claims_officer" and claim.officer_user_id == actor.id
    else:    # "admin"
        allowed = actor.role == "admin"
    if not allowed:
        raise RuleError("You are not allowed to make this change.")

    log_history(claim, actor, claim.status, new_status, note)
    claim.status = new_status


# ---------- creating and editing claims ----------
def validate_claim(user, form, submitting):
    """Check the values typed into the claim form.

    Returns (errors, clean_values):
      errors       - dict {field_name: message}; EMPTY when everything is valid
      clean_values - the converted values (dates as dates, money as Decimal)

    Notes:
      * The claim type is decided by the user's ROLE, never by the form
        (holder = reimbursement, hospital desk = cashless). A user cannot fake it.
      * submitting=True also forbids a future admission date. A draft may keep one.
    """
    if user.role not in SUBMITTERS:
        raise RuleError("Your role cannot create claims.")

    errors = {}
    claim_type = "reimbursement" if user.role == "policyholder" else "cashless"

    policy = find_by_id(Policy, form.get("policy_id"))
    member = find_by_id(Member, form.get("member_id"))
    hospital = find_by_id(Hospital, form.get("hospital_id"))

    # --- policy: a holder may only use their OWN policy ---
    policy_ok = policy is not None and (claim_type == "cashless" or policy.holder_user_id == user.id)
    if not policy_ok:
        errors["policy_id"] = ("Choose one of your policies." if claim_type == "reimbursement"
                               else "Policy not found.")
        policy = None

    # --- member: must be covered by the chosen policy ---
    if member is None or policy is None or member.policy_id != policy.id:
        errors["member_id"] = "This member is not covered by the selected policy."

    # --- hospital ---
    if claim_type == "cashless":
        if hospital is None or hospital.id != user.hospital_id:
            errors["hospital_id"] = "You can only submit for your own hospital."
        elif not hospital.network_status:
            errors["hospital_id"] = "This hospital is not in the cashless network."
    elif hospital is None:
        errors["hospital_id"] = "Choose a hospital."

    if form.get("treatment_type") not in TREATMENTS:
        errors["treatment_type"] = "Choose inpatient or daycare."

    # --- dates and amount ---
    admission = parse_date(form.get("admission_date"))
    discharge = parse_date(form.get("discharge_date"))
    amount = parse_money(form.get("requested_amount"))
    if not admission:
        errors["admission_date"] = "Enter a valid date."
    elif submitting and admission > today():
        errors["admission_date"] = "Admission date cannot be in the future."
    if not discharge:
        errors["discharge_date"] = "Enter a valid date."
    elif admission and discharge < admission:
        errors["discharge_date"] = "Discharge cannot be before admission."
    if amount is None or amount <= 0:
        errors["requested_amount"] = "Enter an amount above 0."

    description = (form.get("description") or "").strip()
    if not description or len(description) > 255:
        errors["description"] = "Enter a description (1-255 characters)."

    clean = dict(claim_type=claim_type,
                 policy_id=policy.id if policy else None,
                 member_id=member.id if member else None,
                 hospital_id=hospital.id if hospital else None,
                 treatment_type=form.get("treatment_type"),
                 admission_date=admission, discharge_date=discharge,
                 requested_amount=amount, description=description)
    return errors, clean


def claim_values(claim):
    """Turn a saved claim back into form-style text values (used to refill the edit form)."""
    names = ("policy_id", "member_id", "hospital_id", "treatment_type",
             "admission_date", "discharge_date", "requested_amount", "description")
    return {name: str(getattr(claim, name)) for name in names}


def save_claim(user, form, claim, submitting):
    """Create a new draft claim, or update the creator's existing draft.

    If submitting=True the claim is also moved to "submitted" in the same step.
    claim is None for a NEW claim, or the draft being edited.
    Returns (saved_claim, errors). When errors is not empty NOTHING was saved.
    """
    errors, clean = validate_claim(user, form, submitting)
    if errors:
        return None, errors

    if claim is None:
        # New claim: save it, write the first history row and an empty document checklist.
        claim = Claim(created_by_user_id=user.id, status="draft", created_at=datetime.now(), **clean)
        db.session.add(claim)
        db.session.flush()                 # flush gives the new claim its id
        log_history(claim, user, None, "draft", "Draft created")
        for doc_type in DOC_TYPES:
            db.session.add(ClaimDocument(claim_id=claim.id, document_type=doc_type,
                                         checklist_status="missing"))
    else:
        # Editing: only the creator may change their own draft.
        if claim.status != "draft" or claim.created_by_user_id != user.id:
            raise RuleError("Only your own draft can be edited.")
        for field, value in clean.items():
            setattr(claim, field, value)
        log_history(claim, user, "draft", "draft", "Draft edited")

    if submitting:
        change_status(claim, "submitted", user, "Submitted")
    return claim, {}


# ---------- workflow actions ----------
# Each action below has the same shape:  action(claim, user, form)
#   claim - the claim being changed        user - the person pressing the button
#   form  - the values posted by the browser
# They change the database objects but do NOT commit: run_action() commits or rolls back.
def submit_draft(claim, user, form):
    """Submit a saved draft. It is validated again, strictly (no future admission date)."""
    errors, _ = validate_claim(user, claim_values(claim), submitting=True)
    if errors:
        raise RuleError(" ".join(errors.values()))
    change_status(claim, "submitted", user, "Submitted")


def respond_more_info(claim, user, form):
    """The submitter answers the officer's question; the claim goes back to "submitted"."""
    note = (form.get("note") or "").strip()
    if not note:
        raise RuleError("Write a short response.")
    change_status(claim, "submitted", user, "Response: " + note)


def set_checklist(claim, user, form):
    """Mark each document as "received" or "missing" (submitter only, draft/more_info claims).

    Only the documents that actually changed are saved, and one history row lists them.
    """
    if claim.created_by_user_id != user.id or claim.status not in ("draft", "more_info"):
        raise RuleError("You cannot change this checklist.")
    current = checklist(claim)
    changes = []
    for doc_type in DOC_TYPES:
        new_value = form.get(doc_type)
        if new_value in ("received", "missing") and new_value != current[doc_type]:
            save_document_status(claim, doc_type, new_value)
            changes.append(f"{doc_type}={new_value}")
    if changes:
        log_history(claim, user, claim.status, claim.status, "Checklist updated: " + ", ".join(changes))


def save_document_status(claim, doc_type, new_status):
    """Set one checklist row. Update it if it exists, otherwise create it."""
    for document in claim.documents:
        if document.document_type == doc_type:
            document.checklist_status = new_status
            return
    db.session.add(ClaimDocument(claim_id=claim.id, document_type=doc_type,
                                 checklist_status=new_status))


def assign(claim, user, form):
    """An officer takes a submitted claim that nobody has taken yet.

    IMPORTANT (the "race condition"): two officers may click at the same moment.
    We use ONE database UPDATE with a WHERE condition ("only if still unassigned").
    The database lets only one of them succeed; the other changes 0 rows and gets
    an error message. That is safer than "check first, then update".
    """
    if user.role != "claims_officer":
        raise RuleError("Only claims officers can assign claims.")
    result = db.session.execute(
        update(Claim)
        .where(Claim.id == claim.id, Claim.status == "submitted", Claim.officer_user_id.is_(None))
        .values(officer_user_id=user.id))
    if result.rowcount != 1:
        raise RuleError("This claim is already assigned or no longer submitted.")
    db.session.refresh(claim)     # reload the claim, because the UPDATE changed it behind our back
    log_history(claim, user, "submitted", "submitted", f"Assigned to {user.display_name}")


def start_review(claim, user, form):
    """The assigned officer starts the review: submitted -> in_review."""
    change_status(claim, "in_review", user, "Review started")


def get_reason(form):
    """Return the written reason from the form, or raise RuleError when it is empty."""
    reason = (form.get("reason") or "").strip()
    if not reason:
        raise RuleError("A written reason is required.")
    return reason


def request_info(claim, user, form):
    """The officer asks for a missing document: in_review -> more_info.

    The chosen document is marked "missing" and the reason is saved in the history.
    """
    doc_type = form.get("document_type")
    reason = get_reason(form)
    if doc_type not in DOC_TYPES:
        raise RuleError("Choose the requested document.")
    change_status(claim, "more_info", user, f"Requested {doc_type}: {reason}")
    save_document_status(claim, doc_type, "missing")


def approve(claim, user, form):
    """The officer approves the claim with an eligible amount: in_review -> approved.

    The eligible amount must be: above 0, not more than the requested amount, and
    not more than the cover still left on the policy.
    """
    reason = get_reason(form)
    eligible = parse_money(form.get("eligible_amount"))
    if eligible is None or eligible <= 0:
        raise RuleError("Eligible amount must be above 0.")
    if eligible > claim.requested_amount:
        raise RuleError("Eligible amount cannot exceed the requested amount.")
    if eligible > remaining_cover(claim.policy):
        raise RuleError("Eligible amount exceeds the remaining fictional cover.")
    change_status(claim, "approved", user, reason)
    claim.eligible_amount = eligible
    claim.decision_reason = reason


def reject(claim, user, form):
    """The officer rejects the claim: in_review -> rejected. A written reason is required."""
    reason = get_reason(form)
    change_status(claim, "rejected", user, reason)
    claim.eligible_amount = Decimal("0.00")
    claim.decision_reason = reason


def settle(claim, user, form):
    """The admin records the simulated payment: approved -> paid.

    The amount typed by the admin must equal the payout the system calculates. The
    payee is the hospital for cashless claims and the policyholder for reimbursements.
    A claim can be settled only once.
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


# ---------- administrator: hospitals, plans, users ----------
def get_text(form, field, field_label):
    """Return a required text field (spaces trimmed) or raise RuleError naming the field."""
    value = (form.get(field) or "").strip()
    if not value:
        raise RuleError(f"{field_label} is required.")
    return value


def save_hospital(form):
    """Create a hospital, or update it when the form contains an id. (No delete, by design.)"""
    hospital = Hospital()
    if form.get("id"):
        hospital = find_by_id(Hospital, form.get("id"))
        if hospital is None:
            raise RuleError("Hospital not found.")
    hospital.name = get_text(form, "name", "Name")
    hospital.city = get_text(form, "city", "City")
    hospital.network_status = form.get("network_status") == "1"
    db.session.add(hospital)


def save_plan(form):
    """Create or update a plan after checking the money values and treatment types."""
    plan = Plan()
    if form.get("id"):
        plan = find_by_id(Plan, form.get("id"))
        if plan is None:
            raise RuleError("Plan not found.")
    limit = parse_money(form.get("annual_limit"))
    deductible = parse_money(form.get("deductible"))
    copay = parse_money(form.get("copay_percent"))
    types = [t for t in form.getlist("covered") if t in TREATMENTS]
    values_ok = None not in (limit, deductible, copay)
    if not values_ok or limit <= 0 or deductible < 0 or not 0 <= copay <= 100 or not types:
        raise RuleError("Enter a limit above 0, deductible 0 or more, "
                        "co-pay 0-100 and one treatment type.")
    plan.name = get_text(form, "name", "Name")
    plan.annual_limit, plan.deductible, plan.copay_percent = limit, deductible, copay
    plan.covered_treatment_types = "|".join(types)
    db.session.add(plan)


POLICY_STATUSES = ("active", "expired")
RELATIONSHIPS = ("self", "spouse", "child", "parent")


def save_policy(form):
    """Create or update a policy: one policyholder, one plan, dates and a status.

    A NEW policy automatically gets the holder as its first covered member ("self"),
    so the holder can start a claim right away. Without a policy the "Policy" drop-down
    on the claim form is empty.
    """
    policy = Policy()
    if form.get("id"):
        policy = find_by_id(Policy, form.get("id"))
        if policy is None:
            raise RuleError("Policy not found.")
    holder = find_by_id(User, form.get("holder_user_id"))
    plan = find_by_id(Plan, form.get("plan_id"))
    start, end = parse_date(form.get("start_date")), parse_date(form.get("end_date"))
    if holder is None or holder.role != "policyholder":
        raise RuleError("Choose a user with the Policyholder role.")
    if plan is None:
        raise RuleError("Choose a plan.")
    if start is None or end is None or end <= start:
        raise RuleError("Enter a start date and a later end date (YYYY-MM-DD).")
    if form.get("status") not in POLICY_STATUSES:
        raise RuleError("Choose a valid policy status.")
    policy.holder_user_id, policy.plan_id = holder.id, plan.id
    policy.start_date, policy.end_date, policy.status = start, end, form.get("status")
    if not policy.id:
        db.session.add(policy)
        db.session.flush()
        db.session.add(Member(policy_id=policy.id, display_name=holder.display_name,
                              relationship="self"))
    else:
        db.session.add(policy)


def save_member(form):
    """Add a covered person (spouse, child, ...) to an existing policy."""
    policy = find_by_id(Policy, form.get("policy_id"))
    if policy is None:
        raise RuleError("Choose a policy.")
    if form.get("relationship") not in RELATIONSHIPS:
        raise RuleError("Choose a valid relationship.")
    name = get_text(form, "display_name", "Member name")
    db.session.add(Member(policy_id=policy.id, display_name=name,
                          relationship=form.get("relationship")))


def save_user(form, admin):
    """Create a user, or change an existing user's name, role, hospital or password.

    * A NEW user must get a password (this is how each user gets their own password).
    * For an existing user the password box is optional: leave it empty to keep the
      old password, or type a new one to RESET it (useful if someone forgot theirs).
    * An admin cannot change their own role (so the last admin cannot lock everyone out).
    """
    user = User()
    if form.get("id"):
        user = find_by_id(User, form.get("id"))
        if user is None:
            raise RuleError("User not found.")
    else:
        user.username = get_text(form, "username", "Username")
        if User.query.filter_by(username=user.username).first():
            raise RuleError("Username already exists.")

    role = form.get("role")
    hospital = find_by_id(Hospital, form.get("hospital_id"))
    if role not in ROLES or (role == "hospital" and hospital is None):
        raise RuleError("Choose a valid role (hospital desks need a hospital).")
    if user.id == admin.id and role != user.role:
        raise RuleError("You cannot change your own role.")

    user.display_name = get_text(form, "display_name", "Display name")
    user.role = role
    user.hospital_id = hospital.id if role == "hospital" else None

    new_password = form.get("password") or ""
    if new_password or not user.id:                 # always needed for a new user
        problem = check_new_password(new_password, user.username)
        if problem:
            raise RuleError(problem)
        user.set_password(new_password)
    db.session.add(user)

    # Optional: a NEW policyholder can be given a plan straight away (no second step needed).
    if not form.get("id") and role == "policyholder" and form.get("plan_id"):
        plan = find_by_id(Plan, form.get("plan_id"))
        if plan is None:
            raise RuleError("Choose a valid plan.")
        start = parse_date(form.get("start_date")) or today()
        end = parse_date(form.get("end_date")) or start.replace(year=start.year + 1)
        if end <= start:
            raise RuleError("The policy end date must be after the start date.")
        db.session.flush()                                    # gives the new user an id
        policy = Policy(holder_user_id=user.id, plan_id=plan.id, start_date=start,
                        end_date=end, status="active")
        db.session.add(policy)
        db.session.flush()
        db.session.add(Member(policy_id=policy.id, display_name=user.display_name,
                              relationship="self"))


def delete_user(form, admin):
    """Delete a user (admin only). Refuses anything that would damage claim records.

    * You cannot delete yourself, and the last administrator can never be deleted.
    * A user who appears in claims, claim history or settlements is kept, because those
      records are an audit trail and must stay valid. Reset their password or change
      their role instead.
    * A policyholder with no claims is deleted together with their (claim-free) policies
      and covered members.
    """
    user = find_by_id(User, form.get("id"))
    if user is None:
        raise RuleError("User not found.")
    if user.id == admin.id:
        raise RuleError("You cannot delete your own account.")
    if user.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        raise RuleError("The last administrator cannot be deleted.")

    in_records = (Claim.query.filter(or_(Claim.created_by_user_id == user.id,
                                         Claim.officer_user_id == user.id)).first()
                  or ClaimHistory.query.filter_by(actor_user_id=user.id).first()
                  or Settlement.query.filter_by(recorded_by_user_id=user.id).first())
    policies = Policy.query.filter_by(holder_user_id=user.id).all()
    if in_records or any(policy.claims for policy in policies):
        raise RuleError(f"{user.username} is used in claim records and cannot be deleted "
                        "(the audit trail must stay intact).")
    for policy in policies:
        for member in policy.members:
            db.session.delete(member)
        db.session.delete(policy)
    db.session.delete(user)


# =====================================================================
# 8. PAGES (ROUTES)  - one function per web page or button
# =====================================================================
# Reading tip:  @app.route("/login")  means "when the browser asks for /login, run the
# function right below". methods=["POST"] means the page only accepts form submissions.

# ---------- login, logout, change password ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    """Show the login page (GET) and check the username + password (POST).

    Each user has their own password hash, so one user's password never works for
    another user. The same message is shown for a wrong username or a wrong
    password, so an attacker cannot find out which usernames exist.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip = request.remote_addr

        # Too many wrong passwords for this username + IP? Refuse for a few minutes (module.py).
        wait = login_guard.seconds_locked(username, ip)
        if wait:
            flash(f"Too many failed attempts. Try again in {wait // 60 + 1} minute(s).", "danger")
            return render_template("login.html"), 429

        user = User.query.filter_by(username=username).first()
        if user is None:
            module.dummy_password_check(check_password_hash)   # same timing as a real check
        if user and user.check_password(password):
            login_guard.record_success(username, ip)
            session.clear()               # start a brand-new session (stops "session fixation")
            session["uid"] = user.id      # remember who logged in
            session["last_seen"] = int(time.time())   # for the idle timeout (module.py)
            return redirect(url_for("dashboard"))
        login_guard.record_failure(username, ip)
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    """Log the user out by clearing the session cookie (POST only, protected by CSRF)."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required()
def change_password():
    """Let ANY logged-in user change their OWN password.

    GET  -> show the form (current password, new password, confirm new password).
    POST -> check_password_change() validates it; if all is well the new password is
            hashed and saved, otherwise an error message is shown and nothing changes.
    The user stays logged in after changing the password.
    """
    if request.method == "POST":
        error = check_password_change(
            g.user,
            request.form.get("current_password", ""),
            request.form.get("new_password", ""),
            request.form.get("confirm_password", ""))
        if error:
            flash(error, "danger")
            return render_template("change_password.html"), 400
        g.user.set_password(request.form["new_password"])
        db.session.commit()
        flash("Your password was changed.", "success")
        return redirect(url_for("dashboard"))
    return render_template("change_password.html")


# ---------- dashboard, policies, hospitals ----------
@app.route("/")
@login_required()
def dashboard():
    """Home page: key numbers, status tabs and the 8 newest claims.

    Everything is calculated from visible_claims(), so each role only sees its own data.
    Claims officers also get "unassigned" and "my open claims" numbers.
    """
    query = visible_claims(g.user)
    extra = {}
    if g.user.role == "claims_officer":
        extra["Unassigned submitted"] = query.filter(
            Claim.status == "submitted", Claim.officer_user_id.is_(None)).count()
        extra["My open claims"] = query.filter(
            Claim.officer_user_id == g.user.id, Claim.status.in_(OPEN_STATUSES)).count()
    recent = query.order_by(Claim.id.desc()).limit(8).all()
    return render_template("dashboard.html", k=kpis(query), extra=extra, recent=recent)





@app.route("/plans")
@login_required()
def plans_catalog():
    """Display all available sample insurance plans."""
    all_plans = Plan.query.order_by(Plan.id).all()

    return render_template(
        "plans_catalog.html",
        plans=all_plans
    )



@app.route("/policies")
@login_required("policyholder")
def policies():
    """Policyholders only: list their own policies with plan details and covered members."""
    my_policies = Policy.query.filter_by(holder_user_id=g.user.id).order_by(Policy.id).all()
    return render_template("policies.html", policies=my_policies, cover=remaining_cover)


@app.route("/hospitals")
@login_required()
def hospitals():
    """Hospital directory: shows which hospitals are in the cashless network."""
    all_hospitals = Hospital.query.order_by(Hospital.name).all()
    return render_template("hospitals.html", hospitals=all_hospitals)


# ---------- claims: list, queue, export ----------
def get_claim(claim_id, lock=False):
    """Load a claim for the current user, or stop with an error.

    404 = the claim does not exist.   403 = it exists but this user may not see it.
    lock=True re-reads the row with "SELECT ... FOR UPDATE" so that two people cannot
    change the same claim at the same moment (used before every workflow action).
    """
    if not db.session.get(Claim, claim_id):
        abort(404)
    if not visible_claims(g.user).filter(Claim.id == claim_id).first():
        abort(403)
    if lock:
        return Claim.query.filter_by(id=claim_id).with_for_update().one()
    return db.session.get(Claim, claim_id)


def apply_filters(query):
    """Read the filters from the page address (?q=...&status=...) and apply them.

    Returns (filtered_query, filter_values). The values are returned so the page can
    show them again in the filter boxes.
    """
    values = {name: request.args.get(name, "").strip()
              for name in ("q", "status", "claim_type", "hospital_id")}
    query = search_claims(query, values["q"], values["status"],
                          values["claim_type"], values["hospital_id"])
    return query.order_by(Claim.id), values


def render_claim_list(query, queue):
    """Show the claims table for a given query. queue=True gives the officer queue layout."""
    filtered, values = apply_filters(query)
    return render_template(
        "claim_list.html", claims=filtered.all(), f=values, queue=queue, today=date.today(),
        counts=status_counts(query), hospitals=Hospital.query.order_by(Hospital.name).all(),
        statuses=STATUSES)


@app.route("/claims")
@login_required()
def claim_list():
    """All claims the user may see, with search and filters."""
    return render_claim_list(visible_claims(g.user), queue=False)


@app.route("/review")
@login_required("claims_officer")
def review_queue():
    """The officer's work queue: submitted, in_review and more_info claims."""
    open_claims = visible_claims(g.user).filter(Claim.status.in_(OPEN_STATUSES))
    return render_claim_list(open_claims, queue=True)


@app.route("/claims/export.csv")
@login_required()
def export_csv():
    """Download the currently filtered claims (only the visible ones) as a CSV file."""
    query, _ = apply_filters(visible_claims(g.user))
    out = io.StringIO()                  # an in-memory text file
    writer = csv.writer(out)
    writer.writerow(["claim_id", "member", "policy_id", "hospital", "type", "treatment", "status",
                     "admission", "discharge", "requested", "eligible", "officer"])
    for claim in query.all():
        officer_name = claim.officer.display_name if claim.officer else ""
        cells = [claim.member.display_name, claim.policy_id, claim.hospital.name, claim.claim_type,
                 claim.treatment_type, claim.status, claim.admission_date, claim.discharge_date,
                 claim.requested_amount, claim.eligible_amount, officer_name]
        writer.writerow([claim.id] + [csv_safe(cell) for cell in cells])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=claims.csv"})


# ---------- claims: create, edit, detail ----------
def show_claim_form(claim, values, errors):
    """Show the claim form. Holders get a list of their policies; hospital desks do not."""
    my_policies = []
    if g.user.role == "policyholder":
        my_policies = Policy.query.filter_by(holder_user_id=g.user.id).all()
    return render_template("claim_form.html", claim=claim, v=values, errors=errors,
                           policies=my_policies, hospitals=Hospital.query.order_by(Hospital.name).all())


def handle_claim_form(claim):
    """Process a posted claim form: save as draft, or submit.

    claim is None for a new claim, or the draft being edited. On any problem the form
    is shown again with the messages (status 400) and NOTHING is saved.
    """
    submitting = request.form.get("action") == "submit"    # which button was pressed
    try:
        saved, errors = save_claim(g.user, request.form, claim, submitting)
        if errors:
            db.session.rollback()
            return show_claim_form(claim, request.form, errors), 400
        db.session.commit()
    except RuleError as error:
        db.session.rollback()
        flash(str(error), "danger")
        return show_claim_form(claim, request.form, {}), 400
    flash("Claim submitted." if submitting else "Draft saved.", "success")
    return redirect(url_for("detail", claim_id=saved.id))


@app.route("/claims/new", methods=["GET", "POST"])
@login_required(*SUBMITTERS)
def new_claim():
    """Create a claim: a reimbursement (policyholder) or a cashless claim (hospital desk)."""
    if request.method == "POST":
        return handle_claim_form(None)
    return show_claim_form(None, {"hospital_id": g.user.hospital_id or ""}, {})


@app.route("/claims/<int:claim_id>/edit", methods=["GET", "POST"])
@login_required(*SUBMITTERS)
def edit_claim(claim_id):
    """Edit your own DRAFT claim. Anything else gives error 403."""
    claim = get_claim(claim_id)
    if claim.status != "draft" or claim.created_by_user_id != g.user.id:
        abort(403)
    if request.method == "POST":
        return handle_claim_form(claim)
    return show_claim_form(claim, claim_values(claim), {})


@app.route("/claims/<int:claim_id>")
@login_required()
def detail(claim_id):
    """The claim page: policy details, documents, warnings, decision, timeline and buttons.

    Review warnings are calculated only for staff (officers and admins).
    """
    claim = get_claim(claim_id)
    is_staff = g.user.role in ("claims_officer", "admin")
    return render_template(
        "claim_detail.html", claim=claim, actions=available_actions(claim, g.user),
        docs=checklist(claim), checks=review_checks(claim) if is_staff else [],
        info=explain(claim), cover=remaining_cover(claim.policy))


# ---------- claims: workflow buttons (all POST-only) ----------
def run_action(claim_id, action, success_message):
    """Run ONE workflow action safely and go back to the claim page.

    1. load the claim (locked, so nobody else can change it right now)
    2. run the action function
    3. success -> commit to the database + show the success message
       RuleError -> roll back (undo everything) + show the error message
    """
    claim = get_claim(claim_id, lock=True)
    try:
        action(claim, g.user, request.form)
        db.session.commit()
        flash(success_message, "success")
    except RuleError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("detail", claim_id=claim_id))


# Each button below is a tiny page: the role check, then run_action() with the action to run.
@app.route("/claims/<int:claim_id>/submit", methods=["POST"])
@login_required(*SUBMITTERS)
def submit(claim_id):
    """Button: submit a saved draft."""
    return run_action(claim_id, submit_draft, "Claim submitted.")


@app.route("/claims/<int:claim_id>/checklist", methods=["POST"])
@login_required(*SUBMITTERS)
def checklist_update(claim_id):
    """Button: save the document checklist."""
    return run_action(claim_id, set_checklist, "Checklist updated.")


@app.route("/claims/<int:claim_id>/respond", methods=["POST"])
@login_required(*SUBMITTERS)
def respond(claim_id):
    """Button: answer the officer's more-info request."""
    return run_action(claim_id, respond_more_info, "Response sent; claim is submitted again.")


@app.route("/claims/<int:claim_id>/assign", methods=["POST"])
@login_required(*STAFF)
def assign_claim(claim_id):
    """Button (officer): take an unassigned claim."""
    return run_action(claim_id, assign, "Claim assigned to you.")


@app.route("/claims/<int:claim_id>/start", methods=["POST"])
@login_required(*STAFF)
def start(claim_id):
    """Button (officer): start the review."""
    return run_action(claim_id, start_review, "Review started.")


@app.route("/claims/<int:claim_id>/more-info", methods=["POST"])
@login_required(*STAFF)
def more_info(claim_id):
    """Button (officer): ask the submitter for a document."""
    return run_action(claim_id, request_info, "More information requested.")


@app.route("/claims/<int:claim_id>/approve", methods=["POST"])
@login_required(*STAFF)
def approve_claim(claim_id):
    """Button (officer): approve with an eligible amount."""
    return run_action(claim_id, approve, "Claim approved.")


@app.route("/claims/<int:claim_id>/reject", methods=["POST"])
@login_required(*STAFF)
def reject_claim(claim_id):
    """Button (officer): reject with a written reason."""
    return run_action(claim_id, reject, "Claim rejected.")


@app.route("/claims/<int:claim_id>/settle", methods=["POST"])
@login_required("admin")
def settle_claim(claim_id):
    """Button (admin): record the simulated payment."""
    return run_action(claim_id, settle, "Simulated settlement recorded.")


# ---------- administration, reports, settlements ----------
@app.route("/admin")
@login_required("admin")
def admin_page():
    """Admin page: lists hospitals, plans and users, each with an add/edit form."""
    return render_template(
        "admin.html", hospitals=Hospital.query.order_by(Hospital.id).all(),
        plans=Plan.query.order_by(Plan.id).all(), users=User.query.order_by(User.id).all(),
        policies=Policy.query.order_by(Policy.id).all(),
        holders=User.query.filter_by(role="policyholder").order_by(User.display_name).all(),
        roles=ROLES, treatments=TREATMENTS, policy_statuses=POLICY_STATUSES,
        relationships=RELATIONSHIPS)


def run_admin_save(save_function, success_message, needs_admin=False):
    """Run one admin save function inside a transaction, then go back to the admin page.

    needs_admin=True passes the logged-in admin to the function (save_user needs it to
    stop admins from changing their own role).
    """
    try:
        if needs_admin:
            save_function(request.form, g.user)
        else:
            save_function(request.form)
        db.session.commit()
        flash(success_message, "success")
    except RuleError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("admin_page"))


@app.route("/admin/hospital", methods=["POST"])
@login_required("admin")
def admin_save_hospital():
    """Button (admin): save a hospital."""
    return run_admin_save(save_hospital, "Hospital saved.")


@app.route("/admin/plan", methods=["POST"])
@login_required("admin")
def admin_save_plan():
    """Button (admin): save a plan."""
    return run_admin_save(save_plan, "Plan saved.")


@app.route("/admin/policy", methods=["POST"])
@login_required("admin")
def admin_save_policy():
    """Button (admin): save a policy (gives a policyholder a plan)."""
    return run_admin_save(save_policy, "Policy saved.")


@app.route("/admin/member", methods=["POST"])
@login_required("admin")
def admin_save_member():
    """Button (admin): add a covered member to a policy."""
    return run_admin_save(save_member, "Member added.")


@app.route("/admin/user", methods=["POST"])
@login_required("admin")
def admin_save_user():
    """Button (admin): create a user (with their own password) or edit / reset one."""
    return run_admin_save(save_user, "User saved.", needs_admin=True)


@app.route("/admin/user/delete", methods=["POST"])
@login_required("admin")
def admin_delete_user():
    """Button (admin only): delete a user that has no claim records."""
    return run_admin_save(delete_user, "User deleted.", needs_admin=True)


@app.route("/reports")
@login_required()
def reports():
    """Reports page: counts and totals by status and type (visible claims only)."""
    rows = report_rows(visible_claims(g.user))
    totals = [sum(row[i] for row in rows) for i in (2, 3, 4, 5)]    # the footer row
    return render_template("reports.html", rows=rows, totals=totals)


@app.route("/settlements")
@login_required()
def settlements():
    """Settlement ledger: totals, approved claims waiting for payment, and payments made."""
    query = visible_claims(g.user)
    return render_template("settlements.html", k=kpis(query),
                           pending=pending_payouts(query), rows=settlement_rows(query))


# ---------- the sidebar badge and the error pages ----------
@app.context_processor
def add_queue_count():
    """Give EVERY template a `queue_count` (the officer's unassigned claims, for the sidebar)."""
    user = getattr(g, "user", None)
    if user is None or user.role != "claims_officer":
        return {"queue_count": None}
    waiting = visible_claims(user).filter(Claim.status == "submitted", Claim.officer_user_id.is_(None))
    return {"queue_count": waiting.count()}


@app.errorhandler(403)
@app.errorhandler(404)
def show_error_page(error):
    """Show a friendly page for 403 (not allowed) and 404 (not found)."""
    return render_template("error.html", e=error), error.code


# =====================================================================
# 9. DEMO DATA AND COMMAND-LINE COMMANDS
# =====================================================================
def read_csv(name):
    """Read data/<name>.csv and return a list of dicts (one dict per row).

    "utf-8-sig" removes the invisible marker Excel adds at the start of a file.
    Empty cells become None.
    """
    with open(DATA_DIR / f"{name}.csv", newline="", encoding="utf-8-sig") as file:
        return [{key: (value if value != "" else None) for key, value in row.items()}
                for row in csv.DictReader(file)]


def money(text):
    """Convert a CSV amount to a 2-place Decimal. None stays None."""
    return None if text is None else Decimal(text).quantize(Decimal("0.01"))


def seed():
    """Fill an empty database with the demo data from the CSV files in data/.

    Every user gets THEIR OWN password: it is read from the "password" column of
    data/users.csv and stored as a salted hash (so two users never share a hash).

    Tables are filled in dependency order: hospitals and plans first, then users,
    policies, members, claims, and finally documents, history and settlements.
    Returns False (and changes nothing) if users already exist.
    """
    if User.query.first():
        return False

    for row in read_csv("hospitals"):
        db.session.add(Hospital(id=int(row["hospital_id"]), name=row["name"], city=row["city"],
                                network_status=row["network_status"] == "1"))
    for row in read_csv("plans"):
        db.session.add(Plan(id=int(row["plan_id"]), name=row["plan_name"],
                            covered_treatment_types=row["covered_treatment_types"],
                            annual_limit=money(row["annual_limit_inr"]),
                            deductible=money(row["deductible_inr"]),
                            copay_percent=money(row["copay_percent"])))
    db.session.flush()     # "flush" sends the rows to the database so later rows can point to them

    for row in read_csv("users"):
        password = row["password"] or ""
        problem = check_new_password(password)
        if problem:
            raise click.UsageError(f"User '{row['username']}': {problem}")
        user = User(id=int(row["user_id"]), username=row["username"],
                    display_name=row["display_name"], role=row["role"],
                    hospital_id=int(row["hospital_id"]) if row["hospital_id"] else None)
        user.set_password(password)          # each user's own password, hashed
        db.session.add(user)
    db.session.flush()

    for row in read_csv("policies"):
        db.session.add(Policy(id=int(row["policy_id"]), holder_user_id=int(row["holder_user_id"]),
                              plan_id=int(row["plan_id"]),
                              start_date=datetime.fromisoformat(row["start_date"]).date(),
                              end_date=datetime.fromisoformat(row["end_date"]).date(),
                              status=row["status"]))
    db.session.flush()
    for row in read_csv("members"):
        db.session.add(Member(id=int(row["member_id"]), policy_id=int(row["policy_id"]),
                              display_name=row["display_name"], relationship=row["relationship"]))
    db.session.flush()

    # The first history event of each claim tells us who created it and when.
    history = sorted(read_csv("claim_history"),
                     key=lambda r: (int(r["claim_id"]), int(r["sequence_no"])))
    first_event = {}
    for event in history:
        first_event.setdefault(int(event["claim_id"]), event)
    for row in read_csv("claims"):
        start = first_event[int(row["claim_id"])]
        db.session.add(Claim(
            id=int(row["claim_id"]), policy_id=int(row["policy_id"]),
            member_id=int(row["member_id"]), hospital_id=int(row["hospital_id"]),
            claim_type=row["claim_type"], treatment_type=row["treatment_type"],
            admission_date=datetime.fromisoformat(row["admission_date"]).date(),
            discharge_date=datetime.fromisoformat(row["discharge_date"]).date(),
            requested_amount=money(row["requested_amount_inr"]),
            eligible_amount=money(row["eligible_amount_inr"]),
            description="Synthetic seed claim", status=row["status"],
            officer_user_id=int(row["officer_user_id"]) if row["officer_user_id"] else None,
            created_by_user_id=int(start["actor_user_id"]),
            created_at=datetime.fromisoformat(start["event_date"])))
    db.session.flush()

    for row in read_csv("claim_documents"):
        db.session.add(ClaimDocument(claim_id=int(row["claim_id"]), document_type=row["document_type"],
                                     checklist_status=row["checklist_status"]))
    for event in history:
        db.session.add(ClaimHistory(
            claim_id=int(event["claim_id"]), sequence_no=int(event["sequence_no"]),
            from_status=event["from_status"], to_status=event["to_status"],
            actor_user_id=int(event["actor_user_id"]), note=event["note"] or "",
            timestamp=datetime.fromisoformat(event["event_date"])))
    for row in read_csv("settlements"):
        db.session.add(Settlement(claim_id=int(row["claim_id"]), payee_type=row["payee_type"],
                                  amount=money(row["amount_inr"]),
                                  recorded_by_user_id=int(row["recorded_by_user_id"]),
                                  recorded_at=datetime.fromisoformat(row["recorded_date"])))
    db.session.commit()
    return True


@app.cli.command("init-db")
def init_db_command():
    """Command `flask --app app init-db`: create all tables from the models above."""
    db.create_all()
    click.echo("Tables created.")


@app.cli.command("seed")
def seed_command():
    """Command `flask --app app seed`: load the demo data (users get their own passwords)."""
    if seed():
        click.echo("Seeded. Passwords come from data/users.csv (see README).")
    else:
        click.echo("Database already has users; nothing changed.")


# =====================================================================
# 10. START THE SERVER
# =====================================================================
if __name__ == "__main__":
    # `python app.py` - for local development only.
    with app.app_context():
        db.create_all()        # create any missing tables
    app.run(debug=True)        # debug=True reloads on code changes and shows error details
