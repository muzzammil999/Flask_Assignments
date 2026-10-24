"""Import the synthetic CSV files into MySQL and expose the `flask init-db` / `flask seed` commands."""
import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import click

from .extensions import db
from .models import (Claim, ClaimDocument, ClaimHistory, Hospital, Member, Plan, Policy,
                     Settlement, User)

DATA = Path(__file__).resolve().parent.parent / "data"


def rows(name, data_dir=DATA):
    """Read data/<name>.csv into dicts, empty cells -> None.
    Why: utf-8-sig strips the BOM from Excel exports; None matches nullable columns. Links: used by every block of seed().
    """
    with open(Path(data_dir) / f"{name}.csv", newline="", encoding="utf-8-sig") as f:
        return [{k: (v if v != "" else None) for k, v in r.items()} for r in csv.DictReader(f)]


def money(x):
    """CSV text -> Decimal with 2 places (None stays None). Why: money never touches float. Links: seed().
    """
    return None if x is None else Decimal(x).quantize(Decimal("0.01"))


def seed(password, data_dir=DATA):
    """Load all CSVs into the DB in foreign-key order and set one password for demo users.
    Why: gives a repeatable demo dataset; first history event supplies each claim's creator/created_at; no-op if users exist so reruns are safe.
    Links: rows, money, models, User.set_password; called by seed_cmd and tests.
    """
    if User.query.first():
        return False
    for r in rows("hospitals", data_dir):
        db.session.add(Hospital(id=int(r["hospital_id"]), name=r["name"], city=r["city"], network_status=r["network_status"] == "1"))
    for r in rows("plans", data_dir):
        db.session.add(Plan(id=int(r["plan_id"]), name=r["plan_name"], covered_treatment_types=r["covered_treatment_types"],
                            annual_limit=money(r["annual_limit_inr"]), deductible=money(r["deductible_inr"]),
                            copay_percent=money(r["copay_percent"])))
    db.session.flush()
    for r in rows("users", data_dir):
        u = User(id=int(r["user_id"]), username=r["username"], display_name=r["display_name"], role=r["role"],
                 hospital_id=int(r["hospital_id"]) if r["hospital_id"] else None)
        u.set_password(password)
        db.session.add(u)
    db.session.flush()
    for r in rows("policies", data_dir):
        db.session.add(Policy(id=int(r["policy_id"]), holder_user_id=int(r["holder_user_id"]), plan_id=int(r["plan_id"]),
                              start_date=datetime.fromisoformat(r["start_date"]).date(),
                              end_date=datetime.fromisoformat(r["end_date"]).date(), status=r["status"]))
    db.session.flush()
    for r in rows("members", data_dir):
        db.session.add(Member(id=int(r["member_id"]), policy_id=int(r["policy_id"]), display_name=r["display_name"],
                              relationship=r["relationship"]))
    db.session.flush()
    history = sorted(rows("claim_history", data_dir), key=lambda r: (int(r["claim_id"]), int(r["sequence_no"])))
    first = {}
    for h in history:
        first.setdefault(int(h["claim_id"]), h)  # first event = creator and creation date
    for r in rows("claims", data_dir):
        cid, start = int(r["claim_id"]), first[int(r["claim_id"])]
        db.session.add(Claim(
            id=cid, policy_id=int(r["policy_id"]), member_id=int(r["member_id"]), hospital_id=int(r["hospital_id"]),
            claim_type=r["claim_type"], treatment_type=r["treatment_type"],
            admission_date=datetime.fromisoformat(r["admission_date"]).date(),
            discharge_date=datetime.fromisoformat(r["discharge_date"]).date(),
            requested_amount=money(r["requested_amount_inr"]), eligible_amount=money(r["eligible_amount_inr"]),
            description="Synthetic seed claim", status=r["status"],
            officer_user_id=int(r["officer_user_id"]) if r["officer_user_id"] else None,
            created_by_user_id=int(start["actor_user_id"]), created_at=datetime.fromisoformat(start["event_date"])))
    db.session.flush()
    for r in rows("claim_documents", data_dir):
        db.session.add(ClaimDocument(claim_id=int(r["claim_id"]), document_type=r["document_type"], checklist_status=r["checklist_status"]))
    for h in history:
        db.session.add(ClaimHistory(claim_id=int(h["claim_id"]), sequence_no=int(h["sequence_no"]), from_status=h["from_status"],
                                    to_status=h["to_status"], actor_user_id=int(h["actor_user_id"]), note=h["note"] or "",
                                    timestamp=datetime.fromisoformat(h["event_date"])))
    for r in rows("settlements", data_dir):
        db.session.add(Settlement(claim_id=int(r["claim_id"]), payee_type=r["payee_type"], amount=money(r["amount_inr"]),
                                  recorded_by_user_id=int(r["recorded_by_user_id"]),
                                  recorded_at=datetime.fromisoformat(r["recorded_date"])))
    db.session.commit()
    return True


def register(app):
    """Attach `flask init-db` and `flask seed` to the app. Links: called from create_app.
    """
    @app.cli.command("init-db")
    def init_db():
        """CLI: create all tables from the models (alternative to schema.sql).
        """
        db.create_all()
        click.echo("Tables created.")

    @app.cli.command("seed")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
                  help="Password given to all demo accounts (min 8 characters).")
    def seed_cmd(password):
        """CLI: prompt for a password (min 8) and run seed(). Why: no default password is stored in code.
        """
        if len(password) < 8:
            raise click.UsageError("Password must be at least 8 characters.")
        click.echo("Seeded." if seed(password) else "Database already has users; nothing changed.")
