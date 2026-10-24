# Trip Planner (Flask + MySQL + SQLAlchemy ORM)

## Features
- Register, login, logout with password hashing
- Private trips and activities; ownership checked on the server
- Trip and activity date/cost validation
- Date-wise activity grouping and live recalculation from saved database rows
- Completed Trips: a trip moves there automatically the day after its end date (home page shows up to 6 as sample trips; full list at `/completed` with destination search). Each shows its photo and whether it stayed within budget; My Trips lists only upcoming/ongoing trips
- Field-level validation messages
- `.env` configuration for database credentials
- CSRF protection on every form
- Optional photo for every trip and activity (PNG/JPG/GIF/WEBP, max 5 MB); add, replace or remove when creating or editing. Files are saved in `uploads/` and only shown to the owner

## Setup (Windows PowerShell)

1. Install Python 3.10+ and MySQL Server.
2. Open PowerShell in this folder.
3. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
4. Install packages:
   ```powershell
   pip install -r requirements.txt
   ```
5. In MySQL Workbench or the MySQL command line, run `schema.sql`.
   This creates `trip_planner_db` and all tables.
6. Back up your existing database and `uploads/` folder before first startup. Open `.env` and set `DB_USER`, `DB_PASSWORD`, and `DB_NAME` to the intended MySQL connection. If `.env` is missing, copy `.env.example` to `.env` and set a strong random `FLASK_SECRET_KEY`. On start-up the app prints warnings if `.env` is missing or unsafe.
   Optional: `DB_HOST`, `DB_PORT`, `DB_NAME`, and `FLASK_DEBUG=1` for development only.
7. Start the app:
   ```powershell
   python app.py
   ```
8. Open http://127.0.0.1:5000 in your browser.
9. Register a new account, log in, create a trip, then add activities.

## Notes
- MySQL must be running before starting Flask.
- `.env` is secret configuration and must not be committed to Git. `.gitignore` excludes it.
- The database password in `.env` must match your local MySQL account.
- `python app.py` creates the database if missing, creates missing tables from the ORM models, and adds missing `image_filename` columns to `trips` / `activities`. It does not delete the retired `place_suggestions` table; keep or remove that legacy table manually only after reviewing and backing up its contents.
- Existing records in `users`, `trips`, and `activities` are preserved. `db.create_all()` does not alter existing column definitions; use Flask-Migrate for future model/schema changes.
- If you use only `schema.sql` on an older database, inspect the existing columns first and add only missing columns (do not blindly rerun `ALTER TABLE` commands).
- Back up the `uploads/` folder along with the database.
- CHECK constraints are enforced on MySQL 8.0.16+.
- Use a strong unique `FLASK_SECRET_KEY`; the placeholder is not suitable for deployment.
- Debug mode is off unless `FLASK_DEBUG=1`. For production, configure HTTPS.
- Costs and budgets are stored as decimal values.
- This app intentionally does not include maps or booking services.

## Documentation
- `ARCHITECTURE.md` explains every file, which route uses which template and table, and how the pieces connect.
- `app.py` uses Flask-SQLAlchemy ORM models (`User`, `Trip`, `Activity`) for application data operations. `schema.sql` is an optional manual setup reference. `ORM_RUN_AND_TEST_GUIDE.md` explains the ORM conversion, startup precautions, every backend function, and the manual test plan.
