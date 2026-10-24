"""ORM models: one class per table of the BRD data model."""
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db

ROLES = ("policyholder", "hospital", "claims_officer", "admin")
STATUSES = ("draft", "submitted", "in_review", "more_info", "approved", "rejected", "paid")


class Hospital(db.Model):
    """Hospital directory entry; network_status True means cashless is allowed."""
    __tablename__ = "hospitals"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    network_status = db.Column(db.Boolean, nullable=False, default=False)


class User(db.Model):
    """Login account with one role; hospital desk users are linked to one hospital."""
    __tablename__ = "users"
    __table_args__ = (db.CheckConstraint(
        "role in ('policyholder','hospital','claims_officer','admin')", name="ck_user_role"),)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"))
    hospital = db.relationship("Hospital")

    def set_password(self, raw):
        """Hash and store a password.
        Why: plain passwords are never persisted. Links: called by services.save_user and seed.seed.
        """
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        """Verify a password against the stored hash.
        Links: used only by routes_main.login.
        """
        return check_password_hash(self.password_hash, raw)


class Plan(db.Model):
    """Fictional plan: limit, deductible, co-pay and covered treatment types (a|b)."""
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    covered_treatment_types = db.Column(db.String(100), nullable=False)
    annual_limit = db.Column(db.Numeric(12, 2), nullable=False)
    deductible = db.Column(db.Numeric(12, 2), nullable=False)
    copay_percent = db.Column(db.Numeric(5, 2), nullable=False)

    def covers(self, treatment):
        """Say whether this plan covers a treatment type.
        Why: covered types are stored as 'a|b' text; this hides the parsing. Links: used by services.review_checks as an officer warning.
        """
        return treatment in self.covered_treatment_types.split("|")


class Policy(db.Model):
    """One holder, one plan, a start/end date and a status (active/expired)."""
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
    """Person covered by exactly one policy."""
    __tablename__ = "members"
    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    relationship = db.Column(db.String(30), nullable=False)


class Claim(db.Model):
    """A cashless or reimbursement request tied to one policy, member and hospital."""
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
    claim_type = db.Column(db.String(20), nullable=False)
    treatment_type = db.Column(db.String(20), nullable=False)
    admission_date = db.Column(db.Date, nullable=False)
    discharge_date = db.Column(db.Date, nullable=False)
    requested_amount = db.Column(db.Numeric(12, 2), nullable=False)
    eligible_amount = db.Column(db.Numeric(12, 2))
    description = db.Column(db.String(255), nullable=False, default="")
    decision_reason = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="draft")
    officer_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    policy = db.relationship("Policy", backref="claims")
    member = db.relationship("Member")
    hospital = db.relationship("Hospital")
    officer = db.relationship("User", foreign_keys=[officer_user_id])
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    documents = db.relationship("ClaimDocument", backref="claim")
    history = db.relationship("ClaimHistory", backref="claim", order_by="ClaimHistory.sequence_no")
    settlement = db.relationship("Settlement", backref="claim", uselist=False)


class ClaimDocument(db.Model):
    """Checklist metadata only: a document type is 'received' or 'missing'."""
    __tablename__ = "claim_documents"
    __table_args__ = (db.UniqueConstraint("claim_id", "document_type"),)
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False)
    document_type = db.Column(db.String(30), nullable=False)
    checklist_status = db.Column(db.String(20), nullable=False)


class ClaimHistory(db.Model):
    """Audit event: who moved a claim from one status to another, when and why."""
    __tablename__ = "claim_history"
    __table_args__ = (db.Index("ix_history_claim_time", "claim_id", "timestamp"),
                      db.UniqueConstraint("claim_id", "sequence_no"))
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False)
    sequence_no = db.Column(db.Integer, nullable=False)
    from_status = db.Column(db.String(20))
    to_status = db.Column(db.String(20), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    note = db.Column(db.String(500), nullable=False, default="")
    timestamp = db.Column(db.DateTime, nullable=False)
    actor = db.relationship("User")


class Settlement(db.Model):
    """Simulated payment for an approved claim; at most one per claim (unique)."""
    __tablename__ = "settlements"
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), unique=True, nullable=False)
    payee_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False)
    recorded_by = db.relationship("User")
