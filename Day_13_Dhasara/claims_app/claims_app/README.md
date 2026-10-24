# Health Insurance Claims Simulator (Flask + SQLAlchemy ORM + MySQL)

Fictional classroom app from the BRD. All data and rules are invented; no real insurance, money or medical files.

## Setup
```bash
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
mysql -u root -p < schema.sql                           # creates claims_db + tables (or use `flask init-db`)
mysql -u root -p -e "CREATE USER 'claims_user'@'localhost' IDENTIFIED BY 'claims_pass'; GRANT ALL ON claims_db.* TO 'claims_user'@'localhost';"
export SECRET_KEY="change-me-long-random"               # Windows: set SECRET_KEY=...
export DATABASE_URL="mysql+pymysql://claims_user:claims_pass@localhost/claims_db"
flask --app wsgi seed                                   # asks for a demo password (min 8 chars), hashes it locally
flask --app wsgi run
python -m pytest                                        # tests run on in-memory SQLite, no MySQL needed
```

## Demo accounts (all use the password you typed at seeding)
| Role | Usernames |
|---|---|
| Policyholder | aasha, bilal, chitra, dev, esha, farhan, gita, harish |
| Hospital desk | city_hospital (1), lotus_hospital (2), green_hospital (3, non-network), sunrise_hospital (4) |
| Claims officer | officer_meera, officer_rahul |
| Administrator | admin_demo |

## Structure
- `app/models.py` ORM tables, FKs, indexes · `app/services.py` every business rule and transition
- `app/routes_*.py` thin routes with role guards · `app/templates/` Jinja pages · `app/seed.py` CSV import
- `schema.sql` MySQL DDL (regenerate: `python make_schema.py`) · `data/` synthetic CSVs · `tests/` pytest

## How BRD rules are enforced
- **Roles/ownership:** `@login_required(role)` on routes plus row checks in `visible_claims()` (holder via `policies.holder_user_id`, hospital via `users.hospital_id`). Forbidden claim = 403.
- **Transitions:** only the `TRANSITIONS` table in `services.py`; `change_status()` checks actor and writes history in the same transaction (rollback on error).
- **Assignment race:** one conditional `UPDATE ... WHERE officer IS NULL AND status='submitted'`; second officer gets an error.
- **Money:** `Decimal` only; `payout = round((eligible - min(eligible, deductible)) x (1 - copay/100), 2)`; approval needs 0 < eligible <= requested and <= remaining cover; settlement must equal computed payout and is unique per claim.
- **Warnings, not auto-decisions:** inactive policy, uncovered treatment, duplicates, missing documents show on the officer's claim page.
- **Security:** hashed passwords, CSRF on all POSTs, secret from env, ORM queries, Jinja auto-escaping.
- **Not included:** document upload is optional in the BRD and omitted; checklist is metadata only.

## Demo path (BRD section 14)
1. `aasha` -> My policies -> New claim -> Submit. 2. `city_hospital` -> New claim (policy 102, member 203, hospital 1); try hospital 2 -> rejected.
3. `officer_meera` -> Review queue -> assign claim 1007 -> start -> request info -> (holder responds) -> approve with eligible amount.
4. `admin_demo` -> open an approved claim (1003 or 1009) -> Record settlement; restart app, data persists.
5. As `aasha` open `/claims/1003` (403); combine search + filters on Claims.
Seed cases: 1002 uncovered treatment, 1005 missing document, 1006 expired policy, 1011/1012 duplicate, 1013 future-date draft.
