# Trip Planner - How everything is connected

This document explains what each file does and which file talks to which.

## 1. Big picture

```
 Browser
   |  (1) request: GET/POST a URL
   v
 app.py  ── Flask route function ──(2)──> Flask-SQLAlchemy ORM models/session ──> MySQL
   |                                                                     users
   |  (3) render_template(...)                                           trips
   v                                                                     activities
 templates/*.html  ──(4)──> HTML sent back to the browser
   |   uses: static/css/style.css, static/js/script.js
   |   photos: <img src="/media/<file>">  ──> media() ──> uploads/ folder
```

Data model: `users 1 ── * trips 1 ── * activities`. Deleting a user deletes their
trips; deleting a trip deletes its activities (`ON DELETE CASCADE`).

## 2. Files

| File | Purpose | Connected to |
|---|---|---|
| `app.py` | The whole backend: config, DB setup, security, uploads, validation, routes | MySQL, every template, `uploads/` |
| `schema.sql` | Optional SQL script for creating the compatible MySQL tables manually | MySQL |
| `.env` (template: `.env.example`) | DB host/port/user/password/name, secret key, debug flag | loaded from `ENV_PATH`; used by `configure_database()`, `SECRET_KEY`, `FLASK_DEBUG`; checked by `check_environment()` |
| `templates/base.html` | Page layout: header/nav, flash messages, footer | extended by every other template; loads CSS + JS |
| `templates/_completed_card.html` | One "completed trip" card | included by `index.html` and `explore.html` |
| `static/css/style.css` | All styling | `base.html` |
| `static/js/script.js` | Keeps trip end date >= start date | `base.html`; targets `data-trip-form` in `trip_form.html` |
| `uploads/` | Saved photos (random file names) | written by `store_image()`, read by `media()` |

## 3. Routes -> function -> template -> tables

| URL | Function in `app.py` | Template | Tables used |
|---|---|---|---|
| `/` | `home` | `index.html` (+ `_completed_card.html`) | trips, activities |
| `/register` | `register` | `register.html` | users (INSERT) |
| `/login` | `login` | `login.html` | users (SELECT) |
| `/logout` (POST) | `logout` | - (redirect) | - |
| `/trips` | `my_trips` | `my_trips.html` | trips, activities (active trips only) |
| `/trips/new` | `create_trip` | `trip_form.html` | trips (INSERT) |
| `/trips/<id>/edit` | `edit_trip` | `trip_form.html` | trips (UPDATE), activities (date check) |
| `/trips/<id>` | `trip_detail` | `trip_detail.html` | trips, activities |
| `/trips/<id>/activities/new` | `add_activity` | `activity_form.html` | activities (INSERT) |
| `/activities/<id>/edit` | `edit_activity` | `activity_form.html` | activities (UPDATE) + trips |
| `/activities/<id>/delete` (POST) | `delete_activity` | - (redirect) | activities (DELETE) |
| `/completed` | `completed_trips_page` | `explore.html` (+ `_completed_card.html`) | trips, activities |
| `/media/<file>` | `media` | - (image bytes) | trips, activities (ownership), `uploads/` |

All pages except `/`, `/register` and `/login` require login (`login_required`).

## 4. Helper functions and who uses them

| Helper (`app.py`) | What it does | Used by |
|---|---|---|
| `User`, `Trip`, `Activity` | ORM models for `users`, `trips`, and `activities`; relationships and constraints | all database routes |
| `configure_database` | builds the SQLAlchemy MySQL URL from `.env` and initializes Flask-SQLAlchemy | module setup |
| `initialize_database` | creates the database if missing, creates ORM tables, and adds missing image columns without deleting old tables | `__main__` (on `python app.py`) |
| `owned_trip` | ORM trip lookup that enforces ownership | `edit_trip`, `trip_detail`, `add_activity` |
| `completed_trips` | ORM aggregation for completed trips and activity totals | `home`, `completed_trips_page` |
| `owned_trip` | trip lookup that enforces ownership | `edit_trip`, `trip_detail`, `add_activity` |
| `completed_trips` | the "end date has passed" query + totals | `home`, `completed_trips_page` |
| `like_pattern` | escape `%` and `_` for searching | `completed_trips` |
| `validate_trip_form` | check destination, dates, budget | `create_trip`, `edit_trip` |
| `validate_activity_form` | check name/date/time/category/place/cost | `add_activity`, `edit_activity` |
| `parse_money` | decimal parsing with range limit | both validators |
| `prepare_image` -> `resolve_image` -> `store_image` / `remove_image_file` | the photo upload pipeline | create/edit trip, add/edit/delete activity |
| `sniff_image_ext` | detect real image type from bytes | `prepare_image` |
| `csrf_token` + `check_csrf` | form token creation / verification | every template form / every POST |
| `inject_globals` | gives templates `csrf_token()` and `categories` | all templates |
| `time_hhmm` (template filter) | show times as `HH:MM` | `trip_detail.html`, `activity_form.html`, `edit_activity` |
| `login_required` | redirect anonymous users to login | most routes |
| `check_environment` | warn about missing/unsafe `.env` settings | `__main__` |

## 5. What "Completed Trips" means

A trip is **completed** automatically once its end date is in the past (it ended
yesterday or earlier). Nothing is moved or stored in the database - two queries
split the same `trips` table by date:

| Query (`app.py`) | Condition | Shown on |
|---|---|---|
| `my_trips()` | `end_date >= today` (upcoming / ongoing) | My Trips |
| `completed_trips()` | `end_date < today` | Home page (sample trips, max 6) and `/completed` |

Only the signed-in user's own trips are included. Each completed card shows the
trip photo (or a 🧳 placeholder), dates, activity count, budget, spent, and a
badge: **within budget** (spent <= budget, shows "Saved") or **over budget**
(shows "Over by"). Because it is calculated on every page load, editing a trip's
dates or an activity's cost updates the lists immediately.

## 6. Typical request flows

**Adding an activity with a photo**
1. Browser opens `/trips/5/activities/new` -> `add_activity` checks `owned_trip(5)` -> renders `activity_form.html`.
2. Browser POSTs the form (with the hidden `_csrf` field and the file).
3. `check_csrf` verifies the token -> `validate_activity_form` checks the fields -> `prepare_image` checks the photo.
4. `resolve_image` saves the file in `uploads/` -> an ORM model object is added and `db.session.commit()` stores the row with `image_filename`.
5. Redirect to `trip_detail`, which reads the rows and shows the photo through `/media/<file>`.

**Viewing a photo** - `<img src="/media/abc….png">` -> `media()` confirms the file name format and that it belongs to one of the user's trips/activities -> `send_from_directory(uploads/)`.

**Budget panel** - `trip_detail` sums the saved `activities.cost` values and subtracts them from `trips.budget` on each page load (negative = "Budget exceeded").

## 7. Security features and where they live

| Protection | Where |
|---|---|
| Password hashing | `register()` / `login()` (Werkzeug) |
| Per-user data isolation | `owned_trip()`, the JOINs in `edit_activity` / `delete_activity` / `media` |
| SQL-injection protection | ORM expressions and bound query parameters; only fixed, escaped DDL is used for database initialization |
| CSRF protection | `csrf_token()`, `check_csrf()`, hidden `_csrf` field in each form |
| Upload safety | `prepare_image()` (type sniffing, 5 MB cap), random names, `IMAGE_NAME_RE`, `MAX_CONTENT_LENGTH` |
| Safe cookies | `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE` |
| Debug off by default | `FLASK_DEBUG` in `.env` |

## 8. Extending the app

- **New activity category:** add it to `CATEGORIES` in `app.py` (validation and dropdown both follow).
- **New page:** add a route in `app.py`, a template extending `base.html`, and a link in `base.html`.
- **New column:** add it to the relevant ORM model and create a Flask-Migrate migration; update `schema.sql` too if you maintain manual SQL setup.

## 9. The `.env` file

| Setting | Meaning | Read by |
|---|---|---|
| `DB_HOST`, `DB_PORT` | where MySQL runs | `configure_database()` |
| `DB_USER`, `DB_PASSWORD` | MySQL login | `configure_database()` |
| `DB_NAME` | database name (auto-created) | `configure_database()`, `initialize_database()` |
| `FLASK_SECRET_KEY` | signs sessions and CSRF tokens | `app.config["SECRET_KEY"]` |
| `FLASK_DEBUG` | `1` = debug mode, `0` = off | `app.run(...)` |

`.env` is secret and listed in `.gitignore`; `.env.example` is the shareable
template. Restart the app after changing either value.
