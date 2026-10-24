# Flask – Complete Topic Guide

Reference city used in every example: **Hyderabad, Telangana, India**.

Each topic has two parts: **what it is (with code)** and **where it appears in this project**.
This project (`weather_dashboard_simple`) has **no database, no login and no posted forms**, so those topics are
explained here with separate, tested examples. They were **not forced into the app**, and the HTML and the working
process of the app were not changed.

| Topic | In this project? |
|---|---|
| Folder structure, configuration, routes, GET, `request.args`, `render_template`, `url_for`, `jsonify`, status codes, server-side validation, Jinja `url_for` | **Yes** – used for real |
| POST, dynamic URLs, Jinja loops/forms, layouts, MySQL, cursor, raw SQL, CRUD, ORM, sessions, login, cookies | **No** – examples only (Sections 3.2, 4, 7-9, 12-16) |

---

## 1. Folder structure

```
weather_dashboard_simple/        <- project root
├── app.py                       <- the Flask app (routes + logic)
├── requirements.txt             <- Flask, requests
├── templates/                   <- HTML files that Flask renders (Jinja)
│   └── index.html
└── static/                      <- files sent as they are (never processed)
    ├── css/style.css
    ├── js/script.js
    └── img/skyline.jpg
```

Rules Flask relies on:

| Folder / file | Rule |
|---|---|
| `templates/` | Must be named exactly this, next to `app.py`. `render_template("x.html")` looks here. |
| `static/` | Must be named exactly this. Everything inside is served at `/static/...`. |
| `app.py` | Any name works, but `app.py` or `wsgi.py` is the convention. |

A bigger project usually grows like this (not needed here):

```
project/
├── app.py            (creates the app, registers blueprints)
├── config.py         (settings)
├── models.py         (ORM classes)
├── db.py             (connection helper)
├── routes/ or blueprints/
├── templates/ (base.html, home.html, partials/...)
└── static/
```

---

## 2. Configuration

Settings live in `app.config` (a dictionary).

```python
app = Flask(__name__)
app.config["SECRET_KEY"] = "long-random-text"      # needed for session, flash, CSRF
app.config["DEBUG"] = True                          # same idea as app.run(debug=True)
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://user:pass@localhost/weatherdb"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # reject uploads over 2 MB
app.config["PERMANENT_SESSION_LIFETIME"] = 3600     # seconds, for permanent sessions
```

Other ways to load config:

```python
app.config.from_object("config.DevConfig")      # a class in config.py
app.config.from_pyfile("settings.py")           # a python file
app.config.from_envvar("APP_SETTINGS")          # path stored in an environment variable
import os; app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]   # best for secrets
```

**Running the server** (`app.run(...)`):

| Option | Meaning |
|---|---|
| `debug=True` | Shows the error page and reloads on code changes. **Never use on a public server.** |
| `host="0.0.0.0"` | Reachable from other computers (default `127.0.0.1` = this PC only). |
| `port=8000` | Change the port (default 5000). |

Command-line alternative: `flask --app app run --debug`.

**In this project:** `app = Flask(__name__)` and `app.run(debug=True)` at the bottom of `app.py`. No secret key is
needed because there are no sessions.

---

## 3. Creating links (routes) – static and dynamic

A **route** connects a URL to a Python function (a *view function*). The decorator `@app.route(...)` creates the link.

### 3.1 Static route (fixed URL)

```python
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return "About page"
```

**In this project:** `/` → `home()` and `/api/weather` → `api_weather()`.

### 3.2 Dynamic route (variable part in the URL)

```python
@app.route("/hello/<name>")                 # /hello/Hyderabad  -> name = "Hyderabad"
def hello(name):
    return f"Hello {name}"

@app.route("/city/<int:city_id>")           # /city/7  -> city_id = 7 (an int)
def city_detail(city_id):
    ...
```

Converters:

| Converter | Matches | Example |
|---|---|---|
| `<name>` / `<string:name>` | any text without `/` | `/hello/Hyderabad` |
| `<int:id>` | whole numbers | `/city/7` |
| `<float:x>` | decimals | `/temp/28.5` |
| `<path:p>` | text including `/` | `/files/a/b/c.txt` |
| `<uuid:u>` | a UUID | `/item/…` |

A wrong type (e.g. `/city/abc`) gives **404** automatically.

### 3.3 Several URLs → one function, and the slash rule

```python
@app.route("/", defaults={"city": "Hyderabad"})
@app.route("/weather/<city>")
def weather(city): ...
```

`"/about/"` (trailing slash) – visiting `/about` redirects to `/about/`. `"/about"` (no slash) – visiting `/about/` gives 404.

### 3.4 Static files

Files in `static/` are served automatically at `/static/<path>`. Never hard-code the path; use `url_for`:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
<script src="{{ url_for('static', filename='js/script.js') }}"></script>
```

This is exactly what `templates/index.html` does.

### 3.5 Redirects, error pages

```python
return redirect(url_for("home"))          # 302 redirect
abort(404)                                # stop and send "Not Found"

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404
```

---

## 4. GET and POST

| | GET | POST |
|---|---|---|
| Purpose | **Read** data / open a page | **Send** data to create or change something |
| Where data travels | In the URL: `?city=Hyderabad` | In the request body (not visible in the URL) |
| Flask reads it with | `request.args` | `request.form` (HTML form) / `request.get_json()` (JSON) / `request.files` |
| Can be bookmarked | Yes | No |
| Should change data? | No (safe) | Yes |
| Size limit | Small (URL length) | Large |

By default a route accepts **GET only** (plus HEAD and OPTIONS). Allow POST explicitly:

```python
@app.route("/cities/add", methods=["GET", "POST"])
def add_city():
    if request.method == "POST":
        name = request.form["name"]        # form field <input name="name">
        ...
        return redirect(url_for("home"))   # Post/Redirect/Get pattern
    return render_template("add_city.html")  # GET: just show the empty form
```

Other methods exist for APIs: `PUT` (replace), `PATCH` (partly update), `DELETE` (remove).
Wrong method → **405 Method Not Allowed**. (Try `POST /` on this project: it returns 405.)

**Post/Redirect/Get:** after a successful POST, always `redirect(...)`. Otherwise pressing F5 re-sends the form.

**In this project:** only GET is used (`fetch("/api/weather?city=Hyderabad")`).

---

## 5. The `request` object and URL information

`request` (imported from `flask`) describes the **incoming** request. It is only usable inside a view function.

| Expression | Meaning | Example for `http://127.0.0.1:5000/api/weather?city=Hyderabad` |
|---|---|---|
| `request.method` | HTTP method | `"GET"` |
| `request.args` | query string (`?a=b`) | `request.args.get("city")` → `"Hyderabad"` |
| `request.form` | form body (POST) | `request.form["name"]` |
| `request.get_json()` | JSON body | `{"city": "Hyderabad"}` → dict |
| `request.files` | uploaded files | `request.files["photo"]` |
| `request.cookies` | cookies sent by the browser | `request.cookies.get("theme")` |
| `request.headers` | HTTP headers | `request.headers.get("User-Agent")` |
| `request.values` | `args` + `form` combined | |
| `request.is_json` | body is JSON? | |

**Request URL parts (the "req_url" topic):**

| Expression | Result for the URL above |
|---|---|
| `request.url` | `http://127.0.0.1:5000/api/weather?city=Hyderabad` |
| `request.base_url` | `http://127.0.0.1:5000/api/weather` (no query string) |
| `request.host_url` | `http://127.0.0.1:5000/` |
| `request.url_root` | `http://127.0.0.1:5000/` |
| `request.path` | `/api/weather` |
| `request.full_path` | `/api/weather?city=Hyderabad` |
| `request.query_string` | `b"city=Hyderabad"` |
| `request.endpoint` | `"api_weather"` (the function name) |
| `request.remote_addr` | client IP |

**Building URLs: `url_for(endpoint, **values)`** – builds the URL *from the function name*, so links never break when you
change a path.

```python
url_for("home")                              # "/"
url_for("api_weather", city="Hyderabad")     # "/api/weather?city=Hyderabad"  (extra args become ?query)
url_for("city_detail", city_id=7)            # "/city/7"                      (matches <int:city_id>)
url_for("static", filename="css/style.css")  # "/static/css/style.css"
url_for("home", _external=True)              # "http://127.0.0.1:5000/" (full URL)
```

**Safe reading of GET values** (what `api_weather()` does):

```python
city = request.args.get("city", "").strip()     # .get() never crashes; default ""
# request.args["city"] would raise 400 Bad Request if missing
page = request.args.get("page", 1, type=int)    # converts to int, falls back to 1
```

**In this project:** `api_weather()` uses `request.args.get("city", "").strip()`; `templates/index.html` uses `url_for('static', ...)`.

---

## 6. Rendering and returning responses

A view function can return:

| Return value | Result |
|---|---|
| `"text"` | HTML/text response, status 200 |
| `render_template("page.html", x=1)` | HTML built from a Jinja template |
| `jsonify({"a": 1})` or a plain `dict` | JSON response (`Content-Type: application/json`) |
| `(body, 404)` | body with a status code |
| `(body, 201, {"X-Header": "v"})` | body, status and headers |
| `redirect(url_for("home"))` | redirect (302) |
| `make_response(...)` | a Response object you can change (cookies, headers) |

```python
@app.route("/city/<name>")
def city(name):
    data = {"name": name, "state": "Telangana", "country": "India"}
    return render_template("city.html", city=data)      # passes variable "city" to the template
```

`render_template("file.html", **variables)` → Flask finds `templates/file.html`, runs Jinja with the variables and returns the HTML.

**In this project:** `home()` renders `index.html`; `api_weather()` returns `jsonify(...)`.

---

## 7. Jinja2 templates – everything you need

Jinja is the template language inside Flask's HTML files. Three kinds of tags:

| Tag | Use |
|---|---|
| `{{ ... }}` | **Output** a value |
| `{% ... %}` | **Logic** (if, for, set, block, include ...) |
| `{# ... #}` | **Comment** (not sent to the browser) |

Jinja **auto-escapes** variables: `<script>` becomes `&lt;script&gt;`, which protects against XSS. Use `{{ html|safe }}`
only for HTML you fully trust.

### 7.1 Variables and attributes

```html
{{ city }}                    <!-- simple variable -->
{{ city.name }}               <!-- dictionary key or object attribute -->
{{ city["name"] }}            <!-- same -->
{{ cities[0] }}               <!-- list index -->
{{ 2 + 3 }}  {{ "Hi " ~ name }}   <!-- maths; ~ joins text -->
```

### 7.2 `if / elif / else`

```html
{% if temp >= 35 %}
  Very hot
{% elif temp >= 25 %}
  Warm
{% else %}
  Cool
{% endif %}

{% if city and city.state %}{{ city.state }}{% endif %}
{% if "India" in countries %}...{% endif %}
{{ "Day" if is_day else "Night" }}        <!-- inline if -->
```

Tests: `is defined`, `is none`, `is even`, `is odd`, `is string`, `is number`, `is divisibleby 3`.
Operators: `==  !=  <  >  <=  >=  and  or  not  in`.

### 7.3 `for` loops (all forms)

```html
<!-- list -->
<ul>
{% for c in cities %}
  <li>{{ c.name }}, {{ c.state }}, {{ c.country }}</li>
{% else %}
  <li>No cities yet.</li>          <!-- runs only if the list is EMPTY -->
{% endfor %}
</ul>

<!-- dictionary -->
{% for key, value in weather.items() %}
  <tr><td>{{ key }}</td><td>{{ value }}</td></tr>
{% endfor %}

<!-- list of lists (unpacking) -->
{% for name, state in [("Hyderabad","Telangana"), ("Pune","Maharashtra")] %}...{% endfor %}

<!-- number range -->
{% for i in range(1, 6) %}{{ i }} {% endfor %}      <!-- 1 2 3 4 5 -->

<!-- filter inside the loop -->
{% for c in cities if c.country == "India" %}...{% endfor %}

<!-- nested loops -->
{% for state in states %}
  <h3>{{ state.name }}</h3>
  {% for city in state.cities %}<p>{{ city }}</p>{% endfor %}
{% endfor %}

<!-- Jinja has no break/continue by default: filter the list in Python or with `if` instead -->
```

**The special `loop` variable (only inside a `for`):**

| Variable | Meaning |
|---|---|
| `loop.index` | current number, starting at **1** |
| `loop.index0` | current number, starting at **0** |
| `loop.revindex` / `loop.revindex0` | numbers counting down to the end |
| `loop.first` | `True` on the first item |
| `loop.last` | `True` on the last item |
| `loop.length` | total number of items |
| `loop.cycle('odd','even')` | alternates the values (zebra rows) |
| `loop.previtem` / `loop.nextitem` | neighbouring items |
| `loop.changed(x)` | `True` when `x` differs from the previous round |

Tested example (output: `<li class="odd">1. Hyderabad, Telangana, INDIA (last)</li>`):

```html
{% for c in cities %}
  <li class="{{ loop.cycle('odd', 'even') }}">
    {{ loop.index }}. {{ c.name }}{% if c.state %}, {{ c.state }}{% endif %}, {{ c.country|upper }}
    {% if loop.last %} (last){% endif %}
  </li>
{% else %}
  <li>No cities yet.</li>
{% endfor %}
```

### 7.4 `set` (variables) and `with`

```html
{% set total = cities|length %}
{% set label %}Weather of {{ city }}{% endset %}     <!-- block set -->
{% with t = 28 %}{{ t }}°C{% endwith %}
```

A variable set **inside** a loop is not visible outside it (Jinja scoping). Use a list/dict or compute it in Python.

### 7.5 Filters (`value|filter`)

| Filter | Example → result |
|---|---|
| `upper` / `lower` / `title` / `capitalize` | `{{ "india"\|title }}` → `India` |
| `length` | `{{ cities\|length }}` → `3` |
| `default` | `{{ state\|default("-") }}` (when missing) / `default("-", true)` (when empty too) |
| `round` | `{{ 28.46\|round(1) }}` → `28.5` |
| `int` / `float` / `string` | type conversion |
| `join` | `{{ ["A","B"]\|join(", ") }}` → `A, B` |
| `first` / `last` / `sort` / `reverse` / `unique` | on lists |
| `sum` / `min` / `max` | on lists of numbers |
| `replace` | `{{ "a-b"\|replace("-", " ") }}` |
| `trim` / `truncate(20)` | cut text |
| `safe` | do not escape (trusted HTML only) |
| `tojson` | `<script>var data = {{ data\|tojson }};</script>` |
| `urlencode` | URL-safe text |
| `format` | `{{ "%s, %s"\|format(city, state) }}` |
| `selectattr` / `rejectattr` / `map` | `{{ cities\|selectattr("country","equalto","India")\|list }}` |
| `groupby` | group items by an attribute |
| `dictsort` | sort a dictionary |

Filters can be chained: `{{ name|trim|title }}`.

### 7.6 Macros (reusable functions)

```html
{% macro weather_card(title, value, unit="") %}
  <div class="card"><p>{{ title }}</p><p>{{ value }}{{ unit }}</p></div>
{% endmacro %}

{{ weather_card("Temperature", 28, "°C") }}
{{ weather_card("Humidity", 68, "%") }}
```

Put macros in `macros.html` and use `{% from "macros.html" import weather_card %}`.

### 7.7 `include` and `import`

```html
{% include "partials/footer.html" %}                  <!-- paste another file here -->
{% from "macros.html" import weather_card %}         <!-- import macros -->
```

### 7.8 Template inheritance → see Section 9 (Layouts)

### 7.9 Useful built-ins inside every template

| Name | Meaning |
|---|---|
| `url_for(...)` | build URLs |
| `request` | the current request (`request.path`, `request.args`) |
| `session` | the session dictionary |
| `g` | per-request storage |
| `config` | `app.config` |
| `get_flashed_messages()` | one-time messages (Section 13.3) |

### 7.10 Whitespace control

`{%- ... -%}` removes the whitespace/new lines before/after the tag.

---

## 8. Jinja with forms

### 8.1 A plain HTML form (what the browser sends)

```html
<form method="post" action="{{ url_for('add_city') }}">
  <label>City</label>
  <input type="text" name="name" value="{{ values.name }}">
  {% if errors.name %}<span class="err">{{ errors.name }}</span>{% endif %}

  <label>State</label>
  <input type="text" name="state" value="{{ values.state }}">

  <label>Country</label>
  <select name="country">
    {% for c in ["India", "Germany", "USA"] %}
      <option value="{{ c }}" {% if values.country == c %}selected{% endif %}>{{ c }}</option>
    {% endfor %}
  </select>

  <button type="submit">Save</button>
</form>
```

Key points:

* `name="..."` is what Flask reads: `request.form["name"]`. **No name = not sent.**
* `method="post"` sends the data in the body. `method="get"` puts it in the URL (`?name=...`).
* `value="{{ values.name }}"` re-fills the box after an error, so the user does not retype.
* Checkbox: `<input type="checkbox" name="agree">` → `request.form.get("agree")` is `"on"` or `None`.
* Several values with the same name: `request.form.getlist("tags")`.
* File upload needs `enctype="multipart/form-data"` and `request.files["photo"]`.
* `action` empty = post back to the same URL.

### 8.2 Reading the form in Flask

```python
name    = request.form.get("name", "").strip()
state   = request.form.get("state", "").strip()
country = request.form.get("country", "").strip()
```

### 8.3 CSRF protection

A real site must protect POST forms against CSRF. The easiest way is **Flask-WTF** (`CSRFProtect(app)` and
`{{ csrf_token() }}` / `form.hidden_tag()` in the form).

---

## 9. Layouts (template inheritance)

Write the common page frame **once** in `base.html`; every page *extends* it and fills the blocks.

`templates/base.html`
```html
<!doctype html>
<html>
<head>
  <title>{% block title %}Weather{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
  {% block head %}{% endblock %}
</head>
<body>
  <nav>
    <a href="{{ url_for('home') }}">Home</a>
    {% if session.get('email') %}
      <a href="{{ url_for('logout') }}">Logout</a>
    {% else %}
      <a href="{{ url_for('login') }}">Login</a>
    {% endif %}
  </nav>

  {% for message in get_flashed_messages() %}<p class="flash">{{ message }}</p>{% endfor %}

  {% block content %}{% endblock %}

  <script src="{{ url_for('static', filename='js/script.js') }}"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

`templates/home.html`
```html
{% extends "base.html" %}                 <!-- must be the FIRST line -->
{% block title %}Cities{% endblock %}
{% block content %}
  <h1>Hyderabad, Telangana, India</h1>
  {{ super() }}                           <!-- optional: keep the parent's block content -->
{% endblock %}
```

Rules: `extends` first; only code inside `{% block %}` appears in a child; blocks can be nested; `{{ super() }}` adds the parent's content.

**In this project:** `index.html` is a single complete page, so no layout is needed. If you add a second page later,
move the shared head/top bar into `base.html`.

---

## 10. Server-side validation

**Why?** JavaScript/HTML checks (`required`, `minlength`) are only for convenience. A user can disable them or call the
URL directly. **The server must always validate again** – never trust data from the browser.

### 10.1 What to validate

| Check | Example |
|---|---|
| Required / not empty | `if not name:` |
| Length | `len(name) < 2` |
| Type / format | `int()`, regular expressions, e-mail pattern |
| Range | age between 1 and 120 |
| Allowed values | country in an allowed list |
| Uniqueness | e-mail not already in the database |
| Cleaning | `.strip()`, `.lower()` |

### 10.2 How it is done in this project

```python
city = request.args.get("city", "").strip()
if len(city) < 2:
    return jsonify({"error": "Please enter a city name."}), 400     # 400 = bad request
```
(and the same rule exists in `script.js` for the user's convenience). Then an unknown city → `404`, an unreachable API → `502`.

### 10.3 Full implementation for an HTML form (tested)

```python
import re

def validate_city(form):
    """Return (errors, cleaned_values). errors is empty when everything is valid."""
    errors = {}
    name    = form.get("name", "").strip()
    state   = form.get("state", "").strip()
    country = form.get("country", "").strip()

    if len(name) < 2:
        errors["name"] = "City name must have at least 2 letters."
    elif not re.fullmatch(r"[A-Za-z .'-]+", name):
        errors["name"] = "Letters only."
    if not country:
        errors["country"] = "Country is required."

    return errors, {"name": name, "state": state, "country": country}


@app.route("/cities/add", methods=["GET", "POST"])
def add_city():
    errors, values = {}, {"name": "", "state": "", "country": ""}
    if request.method == "POST":
        errors, values = validate_city(request.form)
        if not errors:                                   # all good -> save, then redirect
            db.session.add(City(**values))
            db.session.commit()
            flash("City saved.")
            return redirect(url_for("home"))
    # GET, or POST with errors: show the form again with messages and the old values
    return render_template("add_city.html", errors=errors, values=values)
```

Sending `name="H"` and an empty country returns the page (status 200) containing both messages
(*"City name must have at least 2 letters."*, *"Country is required."*); valid data returns a 302 redirect.

### 10.4 Validation for JSON APIs

```python
data = request.get_json(silent=True) or {}
if "city" not in data:
    return jsonify({"error": "city is required"}), 400
if not isinstance(data["city"], str) or len(data["city"].strip()) < 2:
    return jsonify({"error": "city must be text of 2+ letters"}), 422     # 422 = understood but invalid
```

### 10.5 Library option: Flask-WTF / WTForms

```python
class CityForm(FlaskForm):
    name    = StringField("City", validators=[DataRequired(), Length(min=2, max=80)])
    country = StringField("Country", validators=[DataRequired()])
# in the view:  form = CityForm();  if form.validate_on_submit(): ...
```

Also: **validate SQL input by using parameters** (Section 12), never by building SQL text yourself.

---

## 11. HTTP status codes and their families

The first digit is the **family**.

| Family | Meaning | Who is responsible |
|---|---|---|
| **1xx** Informational | request received, keep going | protocol |
| **2xx** Success | request worked | – |
| **3xx** Redirection | go somewhere else | – |
| **4xx** Client error | the request was wrong | the **client** |
| **5xx** Server error | the server (or a service behind it) failed | the **server** |

| Code | Name | Typical Flask use |
|---|---|---|
| 100 | Continue | rarely seen |
| 101 | Switching Protocols | WebSocket upgrade |
| **200** | OK | default success (`home`, successful `api_weather`) |
| **201** | Created | after POST created a record (`return jsonify(row), 201`) |
| 202 | Accepted | work queued |
| **204** | No Content | successful DELETE with no body |
| 301 | Moved Permanently | `redirect(url, 301)` |
| **302** | Found | default `redirect()` |
| 304 | Not Modified | browser cache (static files) |
| 307 / 308 | Temporary / Permanent Redirect | redirect that keeps POST |
| **400** | Bad Request | missing / invalid input (**used here**: city shorter than 2) |
| **401** | Unauthorized | not logged in |
| **403** | Forbidden | logged in but not allowed |
| **404** | Not Found | unknown URL or record (**used here**: city not found) |
| **405** | Method Not Allowed | POST to a GET-only route |
| 409 | Conflict | duplicate (e-mail already registered) |
| 415 | Unsupported Media Type | body is not the expected type |
| **422** | Unprocessable Entity | well-formed but failed validation |
| 429 | Too Many Requests | rate limit |
| **500** | Internal Server Error | unhandled Python exception |
| 501 | Not Implemented | feature missing |
| **502** | Bad Gateway | an upstream service failed (**used here**: weather API unreachable) |
| **503** | Service Unavailable | overloaded / maintenance |
| 504 | Gateway Timeout | upstream too slow |

How to set them in Flask:

```python
return jsonify({"error": "..."}), 404          # tuple form
abort(403)                                      # raises an HTTP error
from http import HTTPStatus; return "", HTTPStatus.NO_CONTENT
@app.errorhandler(500)                          # custom page for a code
def server_error(e): return render_template("500.html"), 500
```

How `script.js` reacts: `if (!response.ok)` is true for every 4xx/5xx; it throws the `error` text sent by Flask.

---

## 12. Databases with MySQL (raw SQL) – connection, cursor, CRUD

> Not used in this project (no database). Shown for learning.

### 12.1 Install and connect

```
pip install PyMySQL        (or mysql-connector-python)
```

```sql
-- run once in MySQL
CREATE DATABASE weatherdb;
USE weatherdb;
CREATE TABLE cities (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    name    VARCHAR(80) NOT NULL,
    state   VARCHAR(80),
    country VARCHAR(80) NOT NULL
);
```

```python
import pymysql

def get_connection():
    """A connection = the open line between Python and the MySQL server."""
    return pymysql.connect(
        host="localhost",
        user="root",
        password="your_password",
        database="weatherdb",
        cursorclass=pymysql.cursors.DictCursor,   # rows come back as dicts, not tuples
    )
```

### 12.2 What is a cursor?

A **connection** is the link to the database. A **cursor** is the object that *runs SQL through that link* and
holds the result.

```python
conn = get_connection()
cur  = conn.cursor()                              # 1. make a cursor
cur.execute("SELECT * FROM cities")               # 2. run SQL
rows = cur.fetchall()                             # 3. read results
cur.close(); conn.close()                         # 4. clean up
```

| Cursor member | Use |
|---|---|
| `cur.execute(sql, params)` | run one statement |
| `cur.executemany(sql, list_of_params)` | run the same statement for many rows |
| `cur.fetchone()` | next row (or `None`) |
| `cur.fetchmany(n)` | next *n* rows |
| `cur.fetchall()` | all remaining rows |
| `cur.rowcount` | rows affected (INSERT/UPDATE/DELETE) |
| `cur.lastrowid` | the AUTO_INCREMENT id of the last INSERT |
| `conn.commit()` | **save** the changes (INSERT/UPDATE/DELETE need this) |
| `conn.rollback()` | undo changes since the last commit |

`DictCursor` → `row["name"]`; the default cursor → `row[1]` (tuple).

### 12.3 Raw SQL safely: use placeholders

```python
# WRONG - SQL injection: city = "x'; DROP TABLE cities; --"
cur.execute(f"SELECT * FROM cities WHERE name = '{city}'")

# RIGHT - the driver escapes the value
cur.execute("SELECT * FROM cities WHERE name = %s", (city,))      # note the tuple, even for 1 value
```

PyMySQL / mysql-connector use `%s` for every type (not `?`, which is SQLite). Table and column names can **not** be
parameters.

### 12.4 CRUD with raw SQL

**C**reate, **R**ead, **U**pdate, **D**elete.

```python
# CREATE
def create_city(name, state, country):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO cities (name, state, country) VALUES (%s, %s, %s)",
                        (name, state, country))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

# READ (all / one)
def list_cities():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, state, country FROM cities ORDER BY name")
            return cur.fetchall()
    finally:
        conn.close()

def get_city(city_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cities WHERE id = %s", (city_id,))
            return cur.fetchone()              # dict or None
    finally:
        conn.close()

# UPDATE
def update_city(city_id, name, state, country):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cities SET name=%s, state=%s, country=%s WHERE id=%s",
                        (name, state, country, city_id))
        conn.commit()
        return cur.rowcount                    # 0 = no such id
    finally:
        conn.close()

# DELETE
def delete_city(city_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cities WHERE id = %s", (city_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
```

**Always** put `WHERE` on UPDATE/DELETE, or every row changes.

### 12.5 Using them in routes

```python
@app.route("/cities")
def cities():
    return render_template("cities.html", cities=list_cities())

@app.route("/cities/add", methods=["POST"])
def cities_add():
    errors, values = validate_city(request.form)           # Section 10
    if errors:
        return render_template("add_city.html", errors=errors, values=values), 400
    create_city(values["name"], values["state"], values["country"])
    return redirect(url_for("cities"))

@app.route("/cities/<int:city_id>/delete", methods=["POST"])   # POST, never GET, for deleting
def cities_delete(city_id):
    if delete_city(city_id) == 0:
        abort(404)
    return redirect(url_for("cities"))
```

### 12.6 Connection management tips

* One connection per request, closed at the end (use `try/finally` or `@app.teardown_appcontext`).
* For many users use a connection pool (SQLAlchemy does this for you).
* Keep passwords out of the code (environment variables).
* Joins and aggregates are plain SQL: `SELECT country, COUNT(*) FROM cities GROUP BY country`.

---

## 13. ORM (SQLAlchemy) – the same CRUD without writing SQL

An **ORM** (Object-Relational Mapper) maps a **table → Python class**, a **row → object**, a **column → attribute**.
Flask uses **Flask-SQLAlchemy**: `pip install Flask-SQLAlchemy PyMySQL`.

```python
from flask_sqlalchemy import SQLAlchemy

app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:password@localhost/weatherdb"
# for quick tests:  "sqlite:///weather.db"
db = SQLAlchemy(app)

class City(db.Model):                                    # table "city"
    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(80), nullable=False)
    state   = db.Column(db.String(80))
    country = db.Column(db.String(80), nullable=False)

with app.app_context():
    db.create_all()                                      # creates missing tables
```

| Operation | ORM code | SQL it replaces |
|---|---|---|
| Create | `db.session.add(City(name="Hyderabad", state="Telangana", country="India")); db.session.commit()` | `INSERT` |
| Read all | `City.query.all()` | `SELECT *` |
| Read one by id | `db.session.get(City, 1)` or `db.get_or_404(City, 1)` | `WHERE id=1` |
| Filter | `City.query.filter_by(country="India").all()` / `City.query.filter(City.name.like("Hyd%"))` | `WHERE` |
| Sort / limit | `City.query.order_by(City.name).limit(10).all()` | `ORDER BY ... LIMIT` |
| First / count | `.first()` / `.count()` | |
| Update | `c = db.session.get(City, 1); c.state = "Telangana"; db.session.commit()` | `UPDATE` |
| Delete | `db.session.delete(c); db.session.commit()` | `DELETE` |

Relationships (one state has many cities):

```python
class State(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    cities = db.relationship("City", backref="state_obj", lazy=True)

class City(db.Model):
    ...
    state_id = db.Column(db.Integer, db.ForeignKey("state.id"))
```

Raw SQL is still possible: `db.session.execute(db.text("SELECT * FROM city WHERE name=:n"), {"n": "Hyderabad"})`.

**Raw SQL vs ORM:** raw SQL = full control and speed for complex queries; ORM = less code, safer by default,
database-independent, easy relationships. After model changes use **Flask-Migrate** (Alembic) instead of `create_all()`.

---

## 14. Sessions

A **session** remembers a user between requests (HTTP itself forgets everything). Flask's session is a dictionary:

```python
from flask import session
app.config["SECRET_KEY"] = "long-random-text"       # REQUIRED

session["email"] = "anu@example.com"                # store
email = session.get("email")                        # read (None if missing)
session.pop("email", None)                          # remove one key
session.clear()                                     # remove everything (logout)
session.permanent = True                            # lives for PERMANENT_SESSION_LIFETIME
```

How it works: Flask **signs** the dictionary with `SECRET_KEY` and stores it in a browser cookie named `session`.
The user can read it but **cannot change it** (the signature would break). So: never put secrets in it, and keep it
small (cookies are limited to about 4 KB). For server-side storage use **Flask-Session**.

---

## 15. Login and logout (tested)

```python
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)     # NEVER store the plain password


@app.route("/register", methods=["POST"])
def register():
    db.session.add(User(email=request.form["email"],
                        password_hash=generate_password_hash(request.form["password"])))
    db.session.commit()
    return "ok", 201


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "")).first()
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            session.clear()                       # start a fresh session (prevents session fixation)
            session["email"] = user.email         # <- this line is "being logged in"
            return redirect(url_for("home"))
        error = "Wrong email or password."        # same message for both cases (do not reveal which)
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
```

**Protecting pages** – a decorator you can put on any route:

```python
from functools import wraps

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "email" not in session:
            return redirect(url_for("login"))          # or abort(401)
        return view(*args, **kwargs)
    return wrapped

@app.route("/cities/add", methods=["GET", "POST"])
@login_required                                         # must be BELOW @app.route
def add_city(): ...
```

Tested behaviour: opening `/cities/add` without login → **302 to `/login`**; wrong password → page with the error;
correct password → **302 to `/`**; after `/logout` the protected page redirects again.

Ready-made option: **Flask-Login** (`login_user(user)`, `logout_user()`, `@login_required`, `current_user`).

---

## 16. Cookies vs sessions

| | **Cookie** | **Flask session** |
|---|---|---|
| What it is | small text stored in the browser | a dictionary Flask keeps for each user |
| Where data lives | in the browser, readable and editable by the user | in a browser cookie **signed** with `SECRET_KEY` (user can read, cannot change); or on the server with Flask-Session |
| Needs `SECRET_KEY` | No | **Yes** |
| Tamper-proof | No (user can edit) | Yes (signed) |
| Typical content | theme, language, "remember me", tracking id | logged-in user id, cart, flash messages |
| Size limit | ~4 KB per cookie | ~4 KB (client-side session) |
| Lifetime | `max_age` / `expires` you choose | browser session, or `PERMANENT_SESSION_LIFETIME` |
| Read in Flask | `request.cookies.get("theme")` | `session.get("email")` |
| Write in Flask | `resp.set_cookie("theme", "dark")` | `session["email"] = ...` |
| Delete | `resp.delete_cookie("theme")` | `session.pop(...)` / `session.clear()` |

Setting and reading a cookie (tested):

```python
@app.route("/theme/<mode>")
def theme(mode):
    resp = make_response("saved")
    resp.set_cookie("theme", mode,
                    max_age=60 * 60 * 24 * 30,   # 30 days
                    httponly=True,               # JavaScript cannot read it
                    samesite="Lax",              # not sent on cross-site POSTs
                    secure=False)                # True when the site uses HTTPS
    return resp

@app.route("/theme")
def read_theme():
    return request.cookies.get("theme", "light")
```

Rule of thumb: **sessions for identity and anything that must not be changed; cookies for harmless preferences.**
In both cases use `httponly=True` and `secure=True` (HTTPS) in production.

**Flash messages** (a session feature): `flash("City saved.")` in one request, and
`{% for m in get_flashed_messages() %}{{ m }}{% endfor %}` in the next page; each message shows once.

---

## 17. Where each topic sits in *this* project

| Topic | File / function | Detail |
|---|---|---|
| App creation | `app.py` – `Flask(__name__)` | |
| Config | `app.py` bottom – `app.run(debug=True)` | no `SECRET_KEY` needed |
| Static route | `home()` → `/`, `api_weather()` → `/api/weather` | no `<variable>` routes |
| GET | both routes; `fetch("/api/weather?city=...")` in `script.js` | |
| `request` | `api_weather()` – `request.args.get("city", "")` | |
| URL building | `templates/index.html` – `url_for('static', filename=...)` | |
| Render / Jinja | `home()` – `render_template("index.html")` | only `{{ url_for() }}` is used |
| JSON | `jsonify(...)` | |
| Status codes | 200, 400, 404, 502 (405 appears if someone POSTs to `/`) | |
| Server validation | `len(city) < 2` → 400; unknown city → 404 | `script.js` repeats the 400 check |
| Second GET route (autocomplete) | `api_suggest()` → `/api/suggest?q=Hyd` | `request.args`, validation (400), `jsonify` list, 502 on API failure |
| Optional query parameters | `api_weather()` reads `country` and `state` besides `city` | `request.args.get("country", "")` |
| Caching | `image_cache` dict in `app.py` | simple in-memory cache |
| Folder structure | `templates/`, `static/css|js|img/` | |

## 18. Quick glossary

* **View function** – the Python function behind a route.
* **Endpoint** – the name of a view function (used by `url_for`).
* **Query string** – the `?key=value&key2=value2` part of a URL.
* **Blueprint** – a way to split routes into several files.
* **Context** – `request`, `session`, `g` only work while a request is being handled.
* **WSGI** – the standard interface between Python web apps and servers (use Gunicorn/Waitress in production, not `app.run`).
* **Idempotent** – repeating the call gives the same result (GET, PUT, DELETE); POST is not.
