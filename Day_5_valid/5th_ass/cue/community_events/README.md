# Community Event Manager (Flask + MySQL)

Simple Flask project. Events and registrations are stored in MySQL.
No JavaScript. The search/filter panel on the home page is display only.

## Setup
1. Open MySQL Workbench, connect to your server, open `schema.sql` and run it
   (lightning bolt). This creates the database `community_events`, the tables
   `events` and `registrations`, and one sample event.
2. Open `app.py` and change `DB_CONFIG` (user and password) to your MySQL login.
3. Install and run:

       pip install -r requirements.txt
       python app.py

   Open http://127.0.0.1:5000

## Image names
Each uploaded image is saved as date + time + extension, e.g. `20261004_104530.jpg`,
in `static/uploads/`. The same name is stored in `events.image_filename`.

## Files
- app.py             routes, SQL queries, Python validation
- schema.sql         database + tables (run in MySQL Workbench)
- templates/         base, index, details, create, edit, register
- static/style.css   styles
- static/uploads/    uploaded event images
