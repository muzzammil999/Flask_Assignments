# Day 6: Flask pages versus Flask API + JavaScript

Two independent folders use the **same Book Shelf domain and fields**. Both connect to MySQL, and each uses a separate database so books entered in one version will not appear in the other. Flask-only runs on port 5000; the API version runs on port 5001.

## Windows setup

Install and start MySQL Server first. Run `mysql_schema.sql` in MySQL Workbench, or from PowerShell with the MySQL command-line client:

```powershell
mysql -u root -p < mysql_schema.sql
```

The script creates both databases and their `books` tables. Enter your MySQL password when prompted.

From this folder:

```text
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

Set the connection settings in PowerShell before starting either app. Replace the example password with the password for your local MySQL account:

```powershell
$env:MYSQL_HOST = '127.0.0.1'
$env:MYSQL_PORT = '3306'
$env:MYSQL_USER = 'root'
$env:MYSQL_PASSWORD = 'your-local-mysql-password'
```

In one terminal, run `cd flask_only` then `python app.py` and open `http://127.0.0.1:5000/`. In another terminal, set the same connection variables, run `cd with_js` then `python app.py`, and open `http://127.0.0.1:5001/`. Each app creates its own `books` table the first time it connects. The optional database-name settings are `FLASK_ONLY_DB_NAME` (default `flask_books_html`) and `WITH_JS_DB_NAME` (default `flask_books_api`). Bootstrap styling uses a CDN; the core app runs without internet.

## Compare the flows

| Action | flask_only | with_js |
| --- | --- | --- |
| List | GET `/` renders HTML with Jinja | GET `/` gives an HTML shell; JS fetches GET `/api/books` |
| Create | POST `/books/new` reads `request.form`, redirects | POST `/api/books` reads JSON, returns JSON + 201 |
| Edit | POST `/books/<id>/edit`, redirects | PUT `/api/books/<id>`, returns JSON + 200 |
| Delete | POST `/books/<id>/delete`, redirects | DELETE `/api/books/<id>`, returns empty body + 204 |

The API also supports GET `/api/books/<id>`. Missing books return JSON + 404. Invalid input returns JSON + 400. Requests without `Content-Type: application/json` on POST/PUT return JSON + 415. The API does not render Jinja for these `/api/` routes.

## Live teaching sequence

1. Make a book in `flask_only`. In the Network tab observe HTML returned after a redirect.
2. Make a book in `with_js`. In the Network tab inspect request URL, method, JSON payload, status 201, and JSON response. The page stays open.
3. Directly visit `http://127.0.0.1:5001/api/books` in the browser to see JSON. For POST/PUT/DELETE, use the UI and Network tab (or an API client).
4. Try empty/short title and a nonexistent ID. Compare 400 versus 404. Disable JavaScript: the API app's page no longer loads books; the Flask-only form still works.
5. Discuss why browser checks cannot replace server validation. Explain that JSON is a data format; API endpoints return data for clients to use.

## Student practice

Add a `genre` field in **both** versions: form, database schema, server validation, display, JSON, and JavaScript DOM rendering. Changing `CREATE TABLE IF NOT EXISTS` does not alter an existing MySQL table, so use `ALTER TABLE books ADD COLUMN genre VARCHAR(80)` in each demo database, or recreate only a disposable classroom database. Do not change or share a production database.

These are local classroom demonstrations: they have no login or CSRF protection and should not be put online as-is.
