# Health Insurance Claims Simulator - SIMPLE version

A beginner-friendly Flask + MySQL app. **One Python file (`app.py`) + one JavaScript file (`static/app.js`).**
It uses the **same database** as the earlier version (`schema.sql`, same tables and columns).
All data and rules are fictional (classroom project).

## What is new in this version
- **Every user has their own password.** Demo passwords are in `data/users.csv` (column `password`) and are stored hashed.
- **Change password page** for every role: `/change-password` (key icon in the top bar, or "Change Password" in the sidebar).
- **Admin can reset a password** (or create a user with their own password) on the Administration page.
- Simpler code: one function per page/button, step-by-step logic, a docstring on every function, comments at the important places.
- The MySQL password is no longer written inside the code: it lives in `.env`.

## Run it
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then edit .env (MySQL password, SECRET_KEY)
mysql -u root -p < schema.sql                         # creates claims_db + tables (or: flask --app app init-db)
flask --app app seed                                  # loads demo data and each user's own password
python app.py                                         # open http://127.0.0.1:5000
python -m pytest                                      # 37 tests, no MySQL needed
```

## Giving a new user a policy
A policyholder only sees **their own** policies in the claim form, so a new user's "Policy" drop-down is empty until
an administrator adds one: Administration -> **Policies** -> choose the policyholder, a plan (for example HDFC ERGO
Optima Secure), the dates and *Active* -> Add. The holder is added as the first covered member automatically; use
"Add a covered member" for a spouse or child.

## Security module (`module.py`)
All security code lives in `module.py`; `app.py` calls it (`module.harden_app(app)` plus a few imports).
| Feature | What it does |
|---|---|
| Login lockout | 5 wrong passwords for a username + IP -> locked 5 minutes (HTTP 429) |
| Security headers | Content-Security-Policy, X-Frame-Options, nosniff, Referrer-Policy, HSTS (production) |
| Cookies | HttpOnly, SameSite=Lax, Secure when `APP_ENV=production` |
| Idle timeout | Auto logout after `SESSION_IDLE_MINUTES` (default 30) |
| No caching | Logged-in pages are sent with `Cache-Control: no-store` |
| Password policy | 8-128 chars, a letter and a number, not a common password, not containing the username |
| SECRET_KEY check | With `APP_ENV=production` the app refuses to start with a weak/missing key |
| Other helpers | `csv_safe` (Excel formula injection), `is_safe_redirect`, constant-time username-timing guard |

Before going live: set `APP_ENV=production`, a random `SECRET_KEY`, run behind HTTPS, and remove the `password`
column from `data/users.csv` (the demo passwords below are public). The lockout counters are in memory - use
Redis/the database if you run several server processes.

## Demo accounts (each has a DIFFERENT password - change them after first login!)
| Role | Username | Password |
|---|---|---|
| Policyholder | aasha | Aasha@2026 |
| Policyholder | bilal | Bilal@2026 |
| Policyholder | chitra | Chitra@2026 |
| Policyholder | dev | Dev@2026 |
| Policyholder | esha | Esha@2026 |
| Policyholder | farhan | Farhan@2026 |
| Policyholder | gita | Gita@2026 |
| Policyholder | harish | Harish@2026 |
| Hospital desk | city_hospital | City_hospital@2026 |
| Hospital desk | lotus_hospital | Lotus_hospital@2026 |
| Hospital desk | green_hospital (non-network) | Green_hospital@2026 |
| Hospital desk | sunrise_hospital | Sunrise_hospital@2026 |
| Claims officer | officer_meera | Officer_meera@2026 |
| Claims officer | officer_rahul | Officer_rahul@2026 |
| Administrator | admin_demo | Admin_demo@2026 |

These are demo passwords written in a text file, so they are NOT secret. For a real deployment, delete the `password`
column from `users.csv`, create users from the Administration page, and let everyone change their password.

## How passwords work
- **Storing:** `User.set_password()` saves a *salted hash* in `users.password_hash`. The real password is never stored, and two
  users with the same password still get different hashes.
- **Logging in:** `login()` compares what you typed with *your own* hash. One user's password never opens another account.
- **Changing your own password:** `change_password()` asks for the current password, the new password and a confirmation.
  `check_password_change()` checks, in order: current password correct -> new password 8-128 characters ->
  confirmation matches -> new is different from current.
- **Forgot a password?** Ask an administrator: Administration -> Users and roles -> type a new password in that user's row -> save.
  (Leave the box empty to keep the old password.)
- **One rule in one place:** `check_new_password()` is used by the change page, the admin form and the seed command.

## Roles and security (unchanged behaviour)
| Layer | Where | What it does |
|---|---|---|
| Role check on pages | `login_required(...)` | not logged in -> login page; wrong role -> 403 |
| Row-level access | `visible_claims()`, `get_claim()` | users only reach their own claims |
| Who may change a status | `TRANSITIONS` + `change_status()` | only the right person can make each step |
| Other | CSRF tokens, hashed passwords, session cookie settings | |

## Files
```
app.py            all Python code, in 10 numbered sections (read top to bottom)
static/app.js     all JavaScript, 5 small helpers (hints, show password, payout preview ...)
static/style.css  styling
templates/        HTML pages (Jinja) - change_password.html is new
data/             demo CSV files (users.csv now has a password column)
schema.sql        MySQL tables (unchanged)   |  make_schema.py regenerates it from the models
tests/test_app.py automatic tests
.env              your settings (MySQL password, SECRET_KEY) - never share it
```

## Reading guide for beginners
1. `app.py` section 3 (models) - see the tables. 2. Section 2 - `TRANSITIONS`, the heart of the workflow.
3. Section 6 - `login_required`. 4. Section 8 - pick one page, e.g. `approve_claim()` -> `run_action()` -> `approve()`.
5. `static/app.js` - each function says what it does and which page uses it.

Small glossary: **route** = a function that answers one web address. **session** = the login cookie.
**g** = a box that lives for one request (holds `g.user`). **decorator** (`@login_required`) = a wrapper that
checks something before your function runs. **ORM** = Python classes instead of SQL text. **transaction** = save everything
or nothing (`commit` / `rollback`).

## Demo path
1. `aasha` -> New claim -> Submit.  2. `officer_meera` -> Review queue -> Assign -> Start -> Request info / Approve.
3. `admin_demo` -> open an approved claim -> Record settlement.  4. As `aasha`, open `/claims/1003` -> 403.
5. Any user -> key icon -> change your password -> log out and log in with the new one.
