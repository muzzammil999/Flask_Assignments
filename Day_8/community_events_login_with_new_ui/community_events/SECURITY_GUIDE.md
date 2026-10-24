# Login & Security Guide (for beginners)

This guide explains **what was added** to the Community Event Manager, **how the
pieces connect**, and **how the security works step by step**. You do not need
any security knowledge to follow it.

---

## 1. What changed?

| File | What changed |
|---|---|
| `app.py` | New login / sign-up / logout pages, the `@login_required` guard, CSRF protection, safer cookie settings. Every function has a docstring. |
| `schema.sql` | One **new table**: `users`. Same database (`community_events`), same `events` and `registrations` tables, nothing deleted. |
| `templates/login.html` | **New** login form (built with your own CSS classes) |
| `templates/signup.html` | **New** sign-up form (built with your own CSS classes) |
| `templates/base.html` | **Lines added** to the menu: *Log in / Sign up* for visitors, *Log out (name)* when logged in |
| `index`, `create`, `edit`, `register` templates | **One line added** to each POST form: the hidden CSRF token. Nothing else changed. |
| `details.html`, `static/style.css` | **Not touched** |
| `requirements.txt` | Unchanged packages (Flask already includes the password-hashing tools) |

**Who can do what now**

| Page | Not logged in | Logged in |
|---|---|---|
| Home `/` and Event details `/events/<id>` | yes | yes |
| Sign up `/signup`, Log in `/login` | yes | redirected home |
| Create `/events/new`, Edit, Delete, Register | **no → sent to login page** | yes |

Your original buttons (*+ Post event*, *Edit*, *Delete*, *Register*) are still
shown to everybody, exactly as in your design. A visitor who clicks one is sent
to the login page and, after logging in, comes straight back to that page.

---

## 2. The big picture: how everything connects

```
        ┌──────────────────────────┐
        │         BROWSER          │   keeps the SESSION COOKIE
        │  (pages, forms, cookie)  │   (signed ticket: "user_id = 3")
        └────────────┬─────────────┘
          request ▲  │  ▲ response (HTML + cookie)
                     ▼  │
        ┌──────────────────────────┐
        │      FLASK  (app.py)     │
        │                          │
        │  1. check_csrf()   ──────┼── runs before EVERY POST
        │  2. @login_required ─────┼── runs before protected pages
        │  3. the route function   │
        │  4. render_template()    │──► templates/*.html  (what the user sees)
        └────────────┬─────────────┘
                     │ get_rows() / change_data()
                     ▼
        ┌──────────────────────────┐
        │   MySQL: community_events│
        │   events                 │
        │   registrations          │
        │   users  (NEW)           │
        └──────────────────────────┘
```

Two places hold information, and it is important not to mix them up:

| Place | What it stores | Who controls it |
|---|---|---|
| **MySQL `users` table** | username + password **hash**. Permanent. | the server |
| **Session cookie** (in the browser) | `user_id`, `username`, the CSRF token, flash messages. Temporary. | the browser holds it, but it is **signed** by the server |

---

## 3. Words you need to know

| Word | Simple meaning |
|---|---|
| **Authentication** | Proving *who you are* (username + password). This is what the login page does. |
| **Hash** | A one-way scramble of the password, e.g. `scrypt:32768:8:1$Gk3...`. You can turn a password into a hash, but **never a hash back into the password**. We store only the hash, so even if someone reads the database they do not get real passwords. |
| **Salt** | Random text mixed in before hashing, so two people with the same password get different hashes. Werkzeug does this automatically. |
| **Session** | Flask's memory of "this browser is logged in as user 3". |
| **Cookie** | A small piece of text the browser stores and sends back with every request. Flask's session lives in a cookie. |
| **Secret key** | A private text only the server knows. Flask uses it to **sign** the cookie. If someone changes the cookie, the signature no longer matches and Flask ignores it. *Signed ≠ encrypted*: a user can read their own cookie, so never put a password in the session. |
| **Decorator** | A line starting with `@` above a function that adds extra behaviour. `@login_required` adds "check the login first". |
| **CSRF** | *Cross-Site Request Forgery*: an evil website tricks **your** browser into sending a request to **our** site while you are logged in (browsers attach your cookie automatically). |
| **CSRF token** | A secret random text in every form. Evil sites cannot see it, so they cannot fake a form. |
| **SQL injection** | Typing SQL code into a text box to attack the database. Blocked by always using `%s` placeholders. |

---

## 4. The five journeys (step by step)

### Journey 1 - Sign up (`/signup`)

```
Browser                         Flask (app.py)                       MySQL
   │  GET /signup                    │
   │────────────────────────────────►│ signup()  → shows signup.html
   │◄────────────────────────────────│ (form contains hidden csrf_token)
   │                                 │
   │  POST /signup (username,        │
   │   password, confirm, token)     │
   │────────────────────────────────►│ check_csrf()  ✔ token matches session
   │                                 │ validate_signup()
   │                                 │    ├─ length / characters
   │                                 │    ├─ password rules, both boxes equal
   │                                 │    └─ SELECT: username free? ──────►│
   │                                 │ generate_password_hash(password)    │
   │                                 │ INSERT username + HASH ────────────►│ saved
   │◄────────────────────────────────│ redirect → /login "Account created"
```

Key lines in `signup()`:

```python
password_hash = generate_password_hash(data["password"])
change_data("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (data["username"], password_hash))
```

The real password exists in memory for a split second and is **never saved**.

### Journey 2 - Log in (`/login`)

```
Browser                         Flask (app.py)                       MySQL
   │  POST /login (username,         │
   │   password, token)              │
   │────────────────────────────────►│ check_csrf()  ✔
   │                                 │ SELECT id, username, password_hash
   │                                 │   WHERE username = %s ─────────────►│
   │                                 │◄────────────────── the user's row ──│
   │                                 │ check_password_hash(saved_hash,
   │                                 │                     typed_password)
   │                                 │   ├─ no match → "Incorrect username
   │                                 │   │              or password."
   │                                 │   └─ match →
   │                                 │        session.clear()
   │                                 │        session["user_id"]  = 3
   │                                 │        session["username"] = "priya"
   │◄────────────────────────────────│ redirect + Set-Cookie: session=<signed>
```

Why it is written this way:

- **`check_password_hash`** hashes the typed password the same way and compares.
  We never "decrypt" anything.
- **One message for both mistakes** ("Incorrect username or password"). If we said
  "no such user", an attacker could discover which usernames exist.
- **`session.clear()` before saving the user id** throws away any old session data
  (including the old CSRF token), so a login always starts from a clean session.
- The line `session["user_id"] = ...` **is** the login. "Logged in" simply means
  "the session contains a user_id".

### Journey 3 - Opening a protected page (the guard)

```python
@app.route("/events/new", methods=["GET", "POST"])
@login_required                    # ← the guard
def create_event():
    ...
```

What `@login_required` does, in plain English:

```
Visitor asks for /events/new
        │
        ▼
Is "user_id" in the session?
   │                    │
  NO                   YES
   │                    │
   ▼                    ▼
flash "Please log in"   run create_event() normally
redirect to
/login?next=/events/new
   │
   ▼  (user logs in)
get_safe_next("/events/new") → redirect back to /events/new
```

- `next=` brings the user back to the page they wanted.
- `get_safe_next()` accepts only addresses that start with a single `/`. Without it
  an attacker could send `/login?next=https://fake-site.example`, and after a real
  login our site would send the user to the fake site.
- The decorator order matters: `@app.route(...)` first (outer), then
  `@login_required` directly above the function.

> **Important:** hiding the *Edit* and *Delete* buttons from visitors (in the
> templates) is only for neatness. A visitor can still type the address by hand.
> The **real** protection is `@login_required` in `app.py`.

### Journey 4 - Every form submit (CSRF protection)

1. When any page is drawn, templates call `{{ csrf_token() }}`.
   `csrf_token()` creates a random value the first time and stores it in the session.
2. That value is written into the form as a hidden field:

   ```html
   <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
   ```
3. When the form is posted, `check_csrf()` (marked `@app.before_request`, so it
   runs before **every** request) compares the value in the form with the value in
   the session. Different or missing → **error 400** and the route never runs.

```
Honest form on our site        →  cookie ✔  + token ✔  → accepted
Evil site posting to our URL   →  cookie ✔  + token ✘  → rejected (400)
```

This is why the delete button on the home page is a tiny form (not a link): a
link can be triggered by anything, a form with a token cannot.

### Journey 5 - Log out

```python
session.clear()
flash("You have logged out.")
```

`session.clear()` removes `user_id`, `username` and the CSRF token. Logout is
`POST` only (with a token), otherwise any website could log you out by showing a
hidden image pointing to `/logout`.

---

## 5. Threats and defences (quick table)

| Danger | Defence | Where in the code |
|---|---|---|
| Someone steals the database | Only password **hashes** are stored | `generate_password_hash` in `signup()` |
| Guessing which usernames exist | Same error message for wrong user / wrong password | `login()` |
| Visitor opens an admin page by typing its address | `@login_required` | above `create_event`, `edit_event`, `register_event`, `delete_event` |
| User edits their cookie to become someone else | Cookie is **signed** with the secret key | `app.secret_key` |
| Script on a page reads the cookie | `SESSION_COOKIE_HTTPONLY = True` | settings at the top |
| Evil site submits our forms | CSRF token + `SameSite=Lax` cookie | `csrf_token()`, `check_csrf()`, `SESSION_COOKIE_SAMESITE` |
| Redirect to a fake site after login | `get_safe_next()` | `login()` |
| SQL injection | Always `%s` placeholders, never string-joining user text into SQL | `get_rows()`, `change_data()` |
| Script injection (XSS) in event titles, etc. | Jinja2 escapes `{{ ... }}` automatically (`<b>` is shown as text) | all templates |
| Two accounts with the same name | `UNIQUE` column + a check before inserting | `users` table, `validate_signup()` |
| Logout/delete triggered by a plain link | These routes accept `POST` only | `logout()`, `delete_event()` |
| Old session reused after login | `session.clear()` first | `login()` |

---

## 6. Function map (where to find things in `app.py`)

| Section | Functions |
|---|---|
| Database | `get_rows`, `change_data` |
| **Security (new)** | `login_required`, `csrf_token`, `check_csrf`, `get_safe_next`, `validate_signup` |
| Helpers | `fix_event`, `get_event`, `parse_date`, `parse_time`, `is_valid_email`, `event_to_form`, `show_errors`, `menu_links` |
| Images | `get_extension`, `check_image`, `save_image` |
| Validation | `validate_event`, `validate_registration` |
| **Routes - login (new)** | `signup`, `login`, `logout` |
| Routes - events | `home`, `event_details`, `create_event`, `edit_event`, `register_event`, `delete_event` |

Every function has a docstring in the same format: a short summary, an
**Explanation**, **Parameters** and **Returns**. Read them like comments.

---

## 7. Try it yourself (5-minute lab)

1. **Not logged in:** open `http://127.0.0.1:5000/events/new` → you land on the
   login page with the message "Please log in to continue."
2. **Sign up** as `priya` with a password of 8+ characters.
3. **Look in MySQL Workbench:** `SELECT * FROM community_events.users;` - the
   `password_hash` column is long scrambled text, not your password.
4. **Log in** → you return to the page you first wanted.
5. **Inspect the cookie:** in the browser press F12 → Application/Storage →
   Cookies. The `session` cookie is there, marked **HttpOnly**.
6. **Test CSRF:** in the browser, F12 → Elements, delete the hidden `csrf_token`
   input from a form and submit it → "Invalid form token" (400).
7. **Log out**, then press the browser Back button and try to create an event →
   you are asked to log in again.

---

## 8. Setup (run once)

1. In MySQL Workbench run `schema.sql` again. It is safe: it only **adds** the
   `users` table and keeps your events.
2. `pip install -r requirements.txt`
3. (Recommended) set a secret key before running:
   - Windows (cmd): `set SECRET_KEY=any-long-random-text-here`
   - Mac/Linux: `export SECRET_KEY=any-long-random-text-here`
4. `python app.py` and open http://127.0.0.1:5000

> **Changing `SECRET_KEY` logs everyone out.** That is expected: the old cookies
> were signed with the old key.

### Exactly what was added to your HTML

Your HTML files were **not rewritten**. Only these lines were added.

**1. The hidden CSRF token** - one line inside each form that sends data
(`create.html`, `edit.html`, `register.html`, the Delete form in `index.html`,
and the Log out form in `base.html`). Without it, every POST is rejected with error 400:

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

**2. The login menu** in `base.html`, right after your *+ Post event* link:

```html
{% if session.get('user_id') %}
<form method="post" action="{{ url_for('logout') }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit">Log out ({{ session['username'] }})</button>
</form>
{% else %}
<a href="{{ url_for('login') }}">Log in</a>
<a href="{{ url_for('signup') }}">Sign up</a>
{% endif %}
```

**3. Two new pages:** `login.html` and `signup.html`.

If you add a new page with a POST form later, remember rule 1: put the hidden
token line inside the form.

---

## 9. What this does NOT do (honest limits)

This is a solid beginner-level login, not a complete user-management product.
Know the limits:

| Limit | What to do later |
|---|---|
| **Any logged-in user can edit or delete any event.** There is no "owner". | Add an `owner_id` column to `events` and check `event["owner_id"] == session["user_id"]` in edit/delete. |
| **No limit on wrong-password attempts** (brute force). | Add a login-attempt counter or the `Flask-Limiter` package. |
| **No HTTPS.** On a real website passwords would travel in plain text without HTTPS. | Host with HTTPS and set `SESSION_COOKIE_SECURE = True`. |
| **No "forgot password" or email check.** | Needs email sending. |
| **Default `SECRET_KEY` is public** (it is in this file). | Always set your own `SECRET_KEY` environment variable on a real server. |
| **MySQL password is written in `app.py`.** | Set the `DB_PASSWORD` environment variable (the code already reads it) and remove the fallback. |
| **`debug=True`** shows detailed errors and can run code. | Only for your own computer. Turn it off on a real server. |
| **Deleted users stay logged in** until their session ends. | Re-check the user in the database on each request if you need this. |
