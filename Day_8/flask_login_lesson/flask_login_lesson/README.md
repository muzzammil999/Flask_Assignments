# Flask login and logout lesson: My Items

## Run on Windows

```bat
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. `classroom.db` is created on first run. For an application shared outside your own computer, set a long random `SECRET_KEY` environment variable; the default key is only for this local lesson. Keep debug mode off outside local development.

## Classroom walkthrough

1. Visit `/dashboard` without logging in: Flask redirects you to `/login`.
2. Register: Flask hashes the password and stores the hash, never the original password.
3. Log in: Flask checks the hash, then stores `user_id` and `username` in a signed session cookie. The cookie is signed, not encrypted; never put a password in it.
4. Add two items. Search and filter using URL query parameters and `request.args.get()`.
5. Log out: `session.clear()` removes login information and redirects home.
6. Try `/dashboard` again. Log in as a second user and see that items belong to their owner.

## Questions for students

- What happens if you type `/dashboard` before logging in?
- Why is the password checked with `check_password_hash`?
- What is stored in the session? What is stored in SQLite?
- Why is logout a POST form rather than a GET link?
- Why does the item query include `owner_id = ?`?

The CSRF token protects POST forms against unwanted cross-site submissions. `session.clear()` rotates the browser's login state when logging in and out. This is a compact classroom example, not a full user management product.
