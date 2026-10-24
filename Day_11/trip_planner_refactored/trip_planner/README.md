# Trip Planner (simple, modular Flask + ORM)

Register, log in, plan trips, add dated activities with costs, watch the budget,
and review completed trips. Built to be **read and learned from**.

## Quick start

1. Install Python 3.10+ and **MySQL** (8.0.16 or newer is best). Make sure MySQL is running.
2. Open `config.py` and set your MySQL password (or set the environment variables
   `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`):

   ```python
   DB_USER = os.environ.get("DB_USER", "root")
   DB_PASSWORD = os.environ.get("DB_PASSWORD", "change-me")   # <- put your password here
   DB_NAME = os.environ.get("DB_NAME", "trip_planner_db")
   ```
3. Install and run:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate            # Windows   (Mac/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   python app.py                     # then open http://127.0.0.1:5000
   ```

The app creates the database (`trip_planner_db`) and its three tables on first
start, so you do not need to run `schema.sql` (it is there for reading, or for
creating the tables by hand in MySQL Workbench).

**Common errors**
* `Access denied for user` -> wrong `DB_USER` / `DB_PASSWORD`.
* `Can't connect to MySQL server` -> MySQL is not running, or `DB_HOST` / `DB_PORT` is wrong.

## The files (read them in this order)

| File | Job | Analogy |
|---|---|---|
| `config.py` | Every setting: database address, secret key, upload folder, limits | The settings panel |
| `schema.sql` | The three tables in plain SQL (reference; the app builds them itself) | The architect's blueprint |
| `models.py` | `User`, `Trip`, `Activity` classes + all reading, saving and validating | The warehouse and its clerk |
| `app.py` | Routes: receives requests, calls models, returns pages | The receptionist |
| `templates/` | HTML pages with blanks that Flask fills in | Mail-merge letters |
| `static/` | CSS and one small JavaScript file | The paint and signage |
| `uploads/` | Photos users upload (not public; served through a permission check) | A locked cupboard |

Rule of thumb: **`app.py` never contains SQL or validation rules; `models.py`
never knows about web pages.** That separation is the whole idea.

## Execution flow

### The big picture

```
 Browser
   │  1. request: "POST /trips/new" + form data
   ▼
 app.py  ── route function create_trip() ──────────────┐
   │  2. ask the model to check the input             │
   ▼                                                   │
 models.py  ── Trip.validate(form)  → (values, errors) │
   │  3. errors? → app.py re-shows the form (go to 7)  │
   │  4. no errors → Trip(...).save()                  │
   ▼                                                   │
 SQLAlchemy ORM (db.session) turns the object into SQL │
   ▼                                                   │
 MySQL database          INSERT INTO trips ...         │
   ▲  5. "ok, saved"                                   │
   │                                                   │
 app.py  ◄─────────────────────────────────────────────┘
   │  6. redirect to /trips   (so Refresh can't re-submit)
   ▼
 Browser asks "GET /trips" → app.py → Trip.active_for(user_id)
   → ORM runs SELECT → Database returns rows → ORM builds Trip objects
   → render_template("my_trips.html", trips=...)  → HTML → Browser   (7)
```

### Step by step: creating a trip

1. **Browser** – the user fills in the form and clicks *Save*; the browser sends
   `POST /trips/new` with the fields and the hidden CSRF token.
2. **`app.py` → `check_csrf()`** – runs before every request; the token must match
   the one in the session, otherwise HTTP 400.
3. **`app.py` → `@login_required`** – is `session["user_id"]` present? If not,
   redirect to the login page.
4. **`app.py` → `create_trip()`** – reads `request.form` and calls
   `Trip.validate(request.form)`.
5. **`models.py` → `Trip.validate()`** – cleans the text, parses dates and money,
   returns `(values, errors)`. Nothing has touched the database yet.
6. **Errors?** – `app.py` renders `trip_form.html` again with the messages and the
   user's typed values. The flow ends here.
7. **No errors** – `app.py` saves the optional photo, builds
   `Trip(owner_id=..., **values)` and calls `trip.save()`.
8. **`models.py` → `save()`** – `db.session.add(trip)` then `db.session.commit()`.
   The ORM writes `INSERT INTO trips ...` over the database connection.
   If anything fails, `rollback()` leaves the database clean.
9. **`app.py`** – `flash("Trip created")` and `redirect(url_for("my_trips"))`.
10. **Browser** – follows the redirect with `GET /trips`.
11. **`app.py` → `my_trips()`** → `Trip.active_for(user_id)` → ORM runs a
    `SELECT` → the database returns rows → the ORM turns them into `Trip` objects.
12. **Template** – `my_trips.html` loops over the trips (`{{ trip.destination }}`,
    `{{ trip.total_cost }}`) and the finished HTML goes back to the browser.

### The same pattern everywhere

| User action | URL | Route in `app.py` | Main model call (`models.py`) | Table |
|---|---|---|---|---|
| Register | `POST /register` | `register()` | `User.validate_registration()`, `User.register()` | users |
| Log in | `POST /login` | `login()` | `User.find_by_username()`, `user.check_password()` | users |
| List trips | `GET /trips` | `my_trips()` | `Trip.active_for()` | trips |
| Create / edit trip | `/trips/new`, `/trips/<id>/edit` | `create_trip()`, `edit_trip()` | `Trip.validate()`, `trip.save()` | trips |
| View itinerary | `GET /trips/<id>` | `trip_detail()` | `Trip.get_owned()`, `trip.activities_by_day()` | trips, activities |
| Add / edit activity | `/trips/<id>/activities/new`, `/activities/<id>/edit` | `add_activity()`, `edit_activity()` | `Activity.validate()`, `activity.save()` | activities |
| Delete activity | `POST /activities/<id>/delete` | `delete_activity()` | `Activity.get_owned()`, `activity.delete()` | activities |
| Completed trips | `GET /completed` | `completed_trips_page()` | `Trip.completed_for()` | trips, activities |
| Show a photo | `GET /media/<file>` | `media()` | `image_belongs_to_user()` | trips, activities |

Privacy is enforced by `Trip.get_owned()` / `Activity.get_owned()`: they only
return a row when it belongs to the logged-in user.

## Glossary (simple definitions + analogies)

| Term | Meaning | Analogy |
|---|---|---|
| **Database** | Organised data stored on disk, surviving restarts. | A filing cabinet: drawers = tables, folders = rows. |
| **MySQL** | A database that runs as a separate server program; the app logs in with a user and password. | An office building with a receptionist. |
| **SQL** | The language databases understand (`SELECT`, `INSERT` ...). | The database's native language. |
| **ORM** | A translator between Python objects and database rows. | An interpreter between you (Python) and the database (SQL). |
| **Model** | A Python class that stands for one table; each object is one row. | A blank form (class) vs. a filled-in form (object). |
| **Database connection** | The open line between the app and the database; its address is in `config.py`. | A phone call that must be dialled before talking. |
| **Cursor** | The pointer that walks through query results row by row. SQLAlchemy manages it for you. | Your finger following a line of text. |
| **Session (database)** | `db.session`: the basket of pending changes; `commit()` saves, `rollback()` cancels. | A shopping basket you pay for at checkout. |
| **Query** | A question to the database, e.g. `Trip.query.filter_by(owner_id=3).all()`. | "Fetch every folder labelled 3." |
| **Primary key / Foreign key** | Unique id of a row / a column pointing to a row in another table. | Passport number / "see passport #123" written on a visa. |
| **Relationship** | Python shortcut across a foreign key: `trip.activities`. | A cross-reference in the filing cabinet. |
| **Flask** | A small toolkit for building web apps in Python. | A kit of web-server parts. |
| **Route / Routing** | A URL mapped to a function with `@app.route(...)`. | A directory: "Accounting? Room 12." |
| **GET / POST** | "Show me a page" / "here is data, act on it". | Reading a menu / handing over your order. |
| **Template (Jinja)** | HTML with blanks (`{{ ... }}`) that Flask fills in. | A mail-merge letter. |
| **Redirect** | Telling the browser to go to a different URL. | "Not here, try the next desk." |
| **Session (login)** | A signed cookie remembering who you are between requests. | A festival wristband. |
| **Flash message** | A one-time notice shown on the next page. | A sticky note that disappears after reading. |
| **Decorator** | `@something` above a function that adds behaviour (`@login_required`). | A security guard stationed in front of a door. |
| **CSRF** | An attack where another site submits a form with your login; stopped by a secret token in each form. | A signature check on every cheque. |
| **Hashing** | One-way scrambling; we store the hash of a password, never the password. | A meat grinder: you can't un-grind it, but you can grind the same input again and compare. |
| **Validation** | Checking input before saving it. | A bouncer at the door. |
| **Environment variable** | A setting kept outside the code (`DATABASE_URL`, `SECRET_KEY`). | A sticky note on the office door. |

## Notes

* The database and tables are created automatically when the app starts.
  `db.create_all()` never changes tables that already exist, so if you change a
  model later, drop the table yourself while learning, or use a migration tool
  such as Flask-Migrate.
* Set a real `SECRET_KEY` before deploying
  (`python -c "import secrets; print(secrets.token_hex(32))"`).
* Photos: PNG/JPG/GIF/WEBP up to 5 MB, saved in `uploads/` under random names and
  shown only to their owner.
* A trip becomes *completed* automatically once its end date is before today.
  This is calculated, not stored.
* Your old MySQL data is not migrated. Use a new `DB_NAME` (the default is the same
  `trip_planner_db` as before!). The old `activities` table has columns named `date`
  and `time`; here they are `activity_date` and `activity_time`. If you reuse the old
  database, either drop the old tables first or rename those two columns.
* Passwords with symbols (`@`, `#`, `/`) work as-is; no escaping is needed.
