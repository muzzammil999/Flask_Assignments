# Community Event Manager (Flask + MySQL) - with login

Simple Flask project. Events, registrations and user accounts are stored in MySQL.
No JavaScript. The search/filter panel on the home page filters events from MySQL (GET form).

Visitors can browse events. Creating, editing, deleting events and registering
for an event require a login.

**New to the login code? Read `SECURITY_GUIDE.md` first.**

## Setup
1. Open MySQL Workbench, connect to your server, open `schema.sql` and run it
   (lightning bolt). This creates the database `community_events`, the tables
   `events`, `registrations` and `users`, and one sample event.
   It is safe to run again on an existing database: it only adds what is missing.
2. Open `app.py` and change `DB_CONFIG` (user and password) to your MySQL login
   (or set the `DB_PASSWORD` environment variable).
3. (Recommended) set a secret key used to sign the login cookie:

       Windows:    set SECRET_KEY=any-long-random-text
       Mac/Linux:  export SECRET_KEY=any-long-random-text

4. Install and run:

       pip install -r requirements.txt
       python app.py

   Open http://127.0.0.1:5000 , click **Sign up**, then **Log in**.

## Image names
Each uploaded image is saved as date + time + extension, e.g. `20261004_104530.jpg`,
in `static/uploads/`. The same name is stored in `events.image_filename`.

## Files
- app.py             routes, SQL queries, Python validation, login + security
- schema.sql         database + tables (run in MySQL Workbench)
- SECURITY_GUIDE.md  beginner explanation of the login flow and security
- templates/         base, index, details, create, edit, register + NEW login, signup
- static/style.css   styles (unchanged)
- static/uploads/    uploaded event images
