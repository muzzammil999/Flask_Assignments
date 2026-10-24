# Community Event Manager

This project converts the supplied Community Event Manager design into a working Flask + MySQL application.

## 1. Project structure

community_event_manager/
├── .env
├── .env.example
├── app.py
├── requirements.txt
├── schema.sql
├── static/
│   ├── css.css
│   ├── js/
│   │   ├── main.js
│   │   └── validation.js
│   └── uploads/
└── templates/
    ├── base.html
    ├── home.html
    ├── event_form.html
    ├── details.html
    └── register.html

## 2. Database

Open MySQL and run:

source schema.sql;

Or copy the contents of schema.sql into MySQL Workbench and execute it.

## 3. Environment file

Create a file named `.env` and add your MySQL details:

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=community_events
SECRET_KEY=change_this_secret_key

## 4. Install packages

python -m venv venv

Windows:
venv\Scripts\activate

Then:

pip install -r requirements.txt

## 5. Run

python app.py

Open:

http://127.0.0.1:5000/

## 6. Main operations

GET:
- View events
- View event details
- Open create/edit/register pages

POST:
- Create an event
- Update an event
- Register for an event

DELETE:
- Delete an event using JavaScript fetch() and the Flask DELETE route

## 7. Event database

The `events` table stores:
- title
- category
- event date
- start time
- venue
- seat capacity
- organizer email
- registration deadline
- description
- image filename

## 8. Registration database

The `registrations` table stores:
- event ID
- full name
- email
- mobile
- seats requested
- registration time

The database prevents the same email from registering twice for the same event.

## 9. Image upload

Allowed formats:
- JPG
- JPEG
- PNG

Maximum size:
- 2 MB

Uploaded images are stored inside:

static/uploads/

## 10. Troubleshooting

- `'datetime.timedelta' object has no attribute 'strftime'` - MySQL returns TIME
  columns as `timedelta`. `app.py` now converts them with `to_time()`.
- Never commit `.env`; it holds your database password.
