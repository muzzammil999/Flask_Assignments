"""Story CRUD using Flask and explicit MySQL queries."""
import os
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-demo-only-change-me")


def connection():
    """The raw SQL version opens a connection for each database operation."""
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ["DB_NAME"],
    )


def fetch_all():
    db = connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, title, author, body FROM stories ORDER BY id DESC")
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def fetch_one(story_id):
    db = connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, title, author, body FROM stories WHERE id = %s",
            (story_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()


def write(sql, values):
    db = connection()
    cursor = db.cursor()
    try:
        cursor.execute(sql, values)
        db.commit()  # Without this, the database change is not permanent.
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def form_values():
    values = {name: request.form.get(name, "").strip()
              for name in ("title", "author", "body")}
    error = None
    if not all(values.values()):
        error = "Fill in every field."
    elif len(values["title"]) > 120 or len(values["author"]) > 80:
        error = "Title must be at most 120 characters; author at most 80."
    return values, error


@app.get("/")
def home():
    return render_template("index.html", stories=fetch_all())


@app.route("/stories/new", methods=["GET", "POST"])
def create_story():
    if request.method == "POST":
        values, error = form_values()
        if error:
            return render_template("form.html", story=values, error=error, heading="New story"), 400
        write("INSERT INTO stories (title, author, body) VALUES (%s, %s, %s)",
              (values["title"], values["author"], values["body"]))
        flash("Story created.")
        return redirect(url_for("home"))
    return render_template("form.html", story={}, heading="New story")


@app.get("/stories/<int:story_id>")
def show_story(story_id):
    story = fetch_one(story_id)
    if story is None:
        abort(404)
    return render_template("detail.html", story=story)


@app.route("/stories/<int:story_id>/edit", methods=["GET", "POST"])
def edit_story(story_id):
    story = fetch_one(story_id)
    if story is None:
        abort(404)
    if request.method == "POST":
        values, error = form_values()
        if error:
            return render_template("form.html", story=values, error=error,
                                   heading="Edit story"), 400
        write("UPDATE stories SET title = %s, author = %s, body = %s WHERE id = %s",
              (values["title"], values["author"], values["body"], story_id))
        flash("Story updated.")
        return redirect(url_for("show_story", story_id=story_id))
    return render_template("form.html", story=story, heading="Edit story")


@app.post("/stories/<int:story_id>/delete")
def delete_story(story_id):
    if fetch_one(story_id) is None:
        abort(404)
    write("DELETE FROM stories WHERE id = %s", (story_id,))
    flash("Story deleted.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
