# Movie Night Planner (Flask + MySQL)

Register, log in, create movies with posters, like them, and see the
most-liked movie on the **Winning Movie** page. The **Users** page lists
every member and the movies they created. Only the creator of a movie
can edit or delete it.

## Run it
1. Run `schema.sql` in MySQL Workbench (creates database `movie_night_db`). The schema has only `users` and `movies` tables; likes are stored in the `movies.likes` JSON column.
2. Keep `.env` private. Replace its placeholder MySQL password and `SECRET_KEY` with your own values. Never commit or share `.env`. `.gitignore` excludes it.
3. `pip install -r requirements.txt`
4. `python app.py` -> open http://127.0.0.1:5000 -> Register -> Log in.

## Files and how they connect
```
app.py            all Python: routes, validate(), database helpers
schema.sql        MySQL tables: users, movies (likes are a column of movies)
.env              local secrets/configuration (keep private; ignored by Git)
.env.example      safe template for local configuration
templates/
  base.html       page frame (top menu, messages) - all pages extend it
  register.html   register()        login.html   login()
  home.html       home()            (uses _card.html for every movie card)
  details.html    details()
  movie_form.html create_movie() and edit_movie() (same form)
  winner.html     winner()          users.html  users()
  error.html      friendly 400/403/404/413 page (show_error)
  _card.html      one movie card      _poster.html  poster image / placeholder
static/
  style.css       the whole look (flat dark theme, no background images)
  uploads/        poster images saved by app.py (name = date_time.ext)
```

## Request flow
```
Browser -> Flask route in app.py -> validate() (checks input)
        -> get_rows()/change_data() (MySQL) -> render_template(page.html)
        -> page extends base.html + style.css -> HTML back to the browser
```
* **Register**: validate("register") -> INSERT users (password saved as a hash) -> login page.
* **Login**: validate("login") -> check hash -> session["user_id"] -> home.
  Every other page uses `@login_required`, which checks that session value.
* **Create / Edit movie**: validate("movie") -> poster saved to static/uploads
  (save_poster) -> INSERT / UPDATE movies.
* **Inline form errors**: invalid movie fields show their own validation message
  immediately below the related title, genres, rating, runtime, synopsis, or poster
  control. Corrected values remain in the form after validation fails.
* **Like**: POST -> adds / removes your user id in the `movies.likes` JSON column (one like per user per movie, no extra table).
* **Genres**: the movie form uses checkboxes (1 to 3); they are saved as `Sci-Fi,Drama` in `movies.genre`.
* **Delete / Edit**: `is_owner(movie)` compares movies.user_id with the logged-in
  user. Anyone else gets an error message and nothing changes (the buttons are also
  hidden for them). Deleting a movie also removes its likes (they are a column of the row)
  and its poster file.
* **Users page**: users() loads all users and all movies, groups the movies by
  creator, and users.html shows Delete only where is_owner(movie) is true.
* **Winning Movie**: top 3 movies ordered by like count (tie -> proposed first).
* **Security**: every POST form carries a CSRF token checked in `check_csrf()`.
* **Extra safety**: poster files must really start like a PNG/JPG (not just have the
  extension), uploads over 4 MB are rejected, the session cookie is HttpOnly +
  SameSite, and errors show a friendly page instead of a crash screen.

## Theme (colours used)
Flat dark theme, no wallpaper or background pictures. Small logo (28px) and avatars (22px).
```
Palette 1: #1B4079 navy  #4D7C8A steel  #7F9C96 mist  #8FAD88 sage  #C7DB94 lime
Palette 2: #010001 black #133336 deep   #285F6B teal  #367D8A light teal  #FFFFFF white
Page = black, cards = deep, borders = teal, buttons = light teal, highlights = lime.
```
Posters without an image show a flat gradient coloured by genre (see `.noposter` in style.css).

## Extra strengthening
* `go_back()` only redirects to pages on this site (ignores a forged Referer header).
* Security headers on every response (`security_headers()`): nosniff, no framing, same-origin referrer.
* If MySQL is off or the password is wrong, a friendly 503 page shows (`database_error()`);
  the real error is printed in the console only.
* Search text is limited to 100 characters; likes read "1 like" / "2 likes".
* Before sharing the site, set `SECRET_KEY` (the app prints a warning if you have not).
