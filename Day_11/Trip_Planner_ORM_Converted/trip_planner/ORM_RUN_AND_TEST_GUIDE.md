# Trip Planner ORM Conversion: Run, Safety, and Test Guide

## 1. What changed

The Trip Planner's application-level database operations now use Flask-SQLAlchemy / SQLAlchemy ORM instead of `mysql-connector-python` cursor queries. The existing Flask routes, URL paths, templates, CSS, JavaScript, field names, form validation, ownership checks, CSRF protection, image-upload flow, and user-facing behavior are retained.

The ORM maps these existing MySQL tables:

- `User` -> `users`
- `Trip` -> `trips`
- `Activity` -> `activities`

`Trip.owner_id` references `users.id`; `Activity.trip_id` references `trips.id`. Cascading relationships and the budget/date/cost constraints are represented in the model definitions. The activity's Python attribute is `activity_date`, mapped to the existing SQL column named `date`, so the MySQL schema and HTML field name remain unchanged.

Most application queries use ORM expressions. Startup uses a small amount of SQLAlchemy `text()` DDL only to create the database before it exists and add missing legacy image columns. It does not issue raw SQL for normal create/read/update/delete application operations.

## 2. Precautions before running

1. **Back up the database first.** In MySQL Workbench, use Server > Data Export and export `trip_planner_db` (or your configured `DB_NAME`) with structure and data. Or use `mysqldump` from a terminal:
   ```bash
   mysqldump -u root -p trip_planner_db > trip_planner_backup.sql
   ```
   Replace the database name and username if yours differ.
2. **Back up uploaded images too.** Copy the project's `uploads/` folder. Database rows store the image filenames, while the image bytes are files on disk.
3. **Do not change `DB_NAME` accidentally.** The application will create a new empty database if the configured database does not exist. Confirm `.env` points to the database you intend to use.
4. **Keep `.env` private.** Set `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, and a strong random `FLASK_SECRET_KEY`. Never upload `.env` to GitHub. `.env.example` is the shareable template.
5. **Use a MySQL account with required permissions.** Initial startup needs permission to create the database if it does not exist, create tables, and add missing `image_filename` columns. If your account is intentionally restricted, create the database manually and grant appropriate table permissions.
6. **Do not run destructive schema commands blindly.** The ORM initializer does not drop the legacy `place_suggestions` table and does not delete user/trip/activity records. Keep that legacy table unless you inspect it and decide to remove it after a backup.
7. **Use a virtual environment.** This prevents the new ORM packages from changing other Python projects on your computer.
8. **Debug mode stays off.** Keep `FLASK_DEBUG=0` unless you are doing local development. Never expose Flask's debug server to the public internet.

## 3. Windows PowerShell setup

Open PowerShell in the extracted `trip_planner` folder.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

Confirm MySQL Server is running. Then check `.env` and make sure its `DB_NAME` matches the intended database. You may run `schema.sql` in MySQL Workbench if you prefer manual setup; it uses the same table names. Do not create a different schema such as the ORM demo's `stories` table: this application requires `users`, `trips`, and `activities`.

Start the app:

```powershell
python app.py
```

The first run creates the configured database if necessary and creates missing tables. Existing tables and records are not intentionally deleted. Open <http://127.0.0.1:5000>.

## 4. ORM model fields

### `User` / `users`

- `id`: auto-increment primary key
- `username`: required, unique, max 80 characters
- `password_hash`: required hashed password (never the plain password)
- `created_at`: database-generated timestamp
- `trips`: ORM relationship to the user's trips

### `Trip` / `trips`

- `id`: auto-increment primary key
- `owner_id`: foreign key to `users.id`
- `destination`: required, max 160 characters
- `start_date`, `end_date`: required dates; end cannot precede start
- `budget`: `DECIMAL(12,2)`, non-negative
- `image_filename`: optional upload filename
- `created_at`: database-generated timestamp
- `owner`, `activities`: ORM relationships

### `Activity` / `activities`

- `id`: auto-increment primary key
- `trip_id`: foreign key to `trips.id`
- `name`: required, max 160 characters
- `activity_date`: Python ORM attribute mapped to MySQL column `date`
- `time`: required MySQL `TIME`
- `category`: required, max 40 characters
- `place`: required, max 200 characters
- `cost`: `DECIMAL(12,2)`, non-negative
- `image_filename`: optional upload filename
- `created_at`: database-generated timestamp
- `trip`: ORM relationship to its trip

## 5. Backend functions and responsibilities

### Configuration and database

- `check_environment()` — prints warnings when `.env`, the Flask secret, or database password settings need attention.
- `time_hhmm(value)` — converts a time value into `HH:MM` for form fields and itinerary display.
- `_server_database_url()` — creates a SQLAlchemy URL for connecting to the MySQL server without selecting a database, used only when creating the database.
- `configure_database()` — configures Flask-SQLAlchemy using `.env` and registers the extension with Flask.
- `initialize_database()` — creates the database if missing, creates missing ORM tables, adds missing `image_filename` columns on legacy tables, and leaves other legacy tables untouched.
- `User`, `Trip`, `Activity` — ORM models for the three application tables. `Trip.to_dict()` and `Activity.to_dict()` preserve the dictionary shape expected by the existing templates.

### Security and shared template helpers

- `csrf_token()` — creates/returns the session's CSRF token.
- `inject_globals()` — exposes `csrf_token()` and the allowed activity `categories` to all templates.
- `check_csrf()` — rejects POST requests with a missing or incorrect CSRF token.
- `login_required(view)` — redirects visitors who are not signed in to the login page.

### Image upload helpers

- `sniff_image_ext(data)` — checks image file signatures and accepts PNG, JPG, GIF, or WEBP only.
- `prepare_image(files, form, errors)` — validates upload size/type and remove-image choice without writing a file.
- `store_image(prep)` — stores validated image bytes under a random filename.
- `remove_image_file(name)` — safely removes a file with a generated-name format.
- `resolve_image(prep, existing)` — decides whether to store a new image, remove the existing one, or keep it.

### Query helpers and validation

- `owned_trip(trip_id)` — uses an ORM query to return a trip only if it belongs to the signed-in user.
- `like_pattern(text_value)` — escapes SQL `LIKE` wildcard characters so a search for `%` or `_` is literal.
- `completed_trips(owner_id, search, limit)` — uses ORM aggregation to calculate completed-trip activity counts and costs.
- `parse_money(raw)` — parses a non-negative amount into a `Decimal` within the supported database range.
- `validate_trip_form(form)` — validates destination, start/end dates, and budget.
- `validate_activity_form(form, trip)` — validates activity name/date/time/category/place/cost and ensures its date is inside the trip dates.

### Routes

- `home()` — renders the landing page and, for signed-in users, up to six completed trips.
- `register()` — validates account details, checks username uniqueness, hashes the password, and inserts a `User` through the ORM.
- `login()` — retrieves a `User` through the ORM and verifies the password hash.
- `logout()` — clears the session; the route is POST-only and protected by CSRF.
- `my_trips()` — lists the current user's active trips and computes each trip's activity cost using an ORM subquery.
- `create_trip()` — validates the trip form and creates a `Trip`, including its optional photo filename.
- `edit_trip(trip_id)` — checks ownership, validates dates against existing activities, and updates a trip.
- `trip_detail(trip_id)` — loads the owned trip and activities, groups activities by date, and calculates budget totals.
- `add_activity(trip_id)` — validates and creates an activity for an owned trip.
- `edit_activity(activity_id)` — checks ownership through an ORM join and updates an activity.
- `delete_activity(activity_id)` — deletes an owned activity and then removes its associated image file.
- `completed_trips_page()` — searches and lists completed trips belonging to the signed-in user.
- `media(filename)` — serves an uploaded image only when its generated filename is valid and it belongs to the signed-in user.
- `too_large(_error)` — renders the friendly error page for requests exceeding the upload limit.
- `bad_request(_error)` — renders the friendly error page for invalid CSRF requests.
- `not_found(_error)` — renders the friendly error page for unknown routes or inaccessible photos.
- `server_error(_error)` — renders the friendly error page for unexpected server errors.

## 6. Manual test checklist

Perform these tests using a fresh test account first. Avoid deleting real records while verifying the project.

1. Visit `/` and confirm the home page loads.
2. Register a new user. Confirm the account is created and the password is stored as a hash.
3. Try registering the same username again; confirm the duplicate warning appears.
4. Log in with the correct password; then try an incorrect password and confirm it is rejected.
5. Create a trip with a valid destination, date range, and budget. Confirm it appears in My Trips.
6. Try an end date earlier than the start date and a negative/invalid budget; confirm field-level validation appears.
7. Open the trip and add an activity inside the trip dates. Confirm its time, category, place, and cost display correctly.
8. Try an activity date outside the trip range; confirm validation prevents it.
9. Add a valid image, view it, replace it, and remove it. Confirm other users cannot access that image URL.
10. Edit a trip's dates so they would exclude an existing activity; confirm the date change is blocked.
11. Check that the budget total updates after adding, editing, and deleting activities.
12. Set a trip end date in the past using test data and confirm it appears on Completed Trips and the home page.
13. Create a second user and confirm they cannot edit or view the first user's private trips and activities.
14. Log out and confirm protected routes redirect to login.
15. Restart the app and confirm saved trips, activities, and photos remain available.

## 7. If startup fails

- **`ModuleNotFoundError: flask_sqlalchemy`** — activate the project's virtual environment and run `pip install -r requirements.txt`.
- **`ModuleNotFoundError: pymysql`** — run `pip install PyMySQL` inside the same environment.
- **Access denied** — verify `DB_USER`, `DB_PASSWORD`, host, and permissions in `.env`.
- **Can't connect to MySQL** — start the MySQL service and verify `DB_HOST` / `DB_PORT`.
- **Unknown database** — verify `DB_NAME`; the app creates it automatically only if the configured account has permission.
- **Existing table missing `image_filename`** — startup attempts to add it. If the MySQL account cannot alter tables, add the missing column after backing up and confirming it is absent.
- **Unexpected ORM/schema mismatch** — stop the app and back up first. `db.create_all()` creates missing tables but does not rewrite existing columns. Use reviewed migrations for structural changes rather than dropping tables.

## 8. Scope and verification note

The Python source is syntax-compiled during packaging. A live end-to-end test requires the target machine's MySQL server and the packages in `requirements.txt`; those services are not bundled in this ZIP. Follow the checklist above after configuring the local database.
