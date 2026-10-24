"""The same Story CRUD using Flask-SQLAlchemy's ORM."""
import os
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

load_dotenv()


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class Story(db.Model):
    __tablename__ = "stories"  # Both versions use the same MySQL table.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    author: Mapped[str] = mapped_column(String(80), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-demo-only-change-me")
# URL.create handles special characters in the database password correctly.
app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
    "mysql+mysqlconnector",
    username=os.environ["DB_USER"],
    password=os.environ.get("DB_PASSWORD", ""),
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", "3306")),
    database=os.environ["DB_NAME"],
)
db.init_app(app)


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
    stories = db.session.execute(db.select(Story).order_by(Story.id.desc())).scalars().all()
    return render_template("index.html", stories=stories)


@app.route("/stories/new", methods=["GET", "POST"])
def create_story():
    if request.method == "POST":
        values, error = form_values()
        if error:
            return render_template("form.html", story=values, error=error, heading="New story"), 400
        db.session.add(Story(**values))  # A new Python object becomes pending database work.
        db.session.commit()  # Commit makes the change persist.
        flash("Story created.")
        return redirect(url_for("home"))
    return render_template("form.html", story={}, heading="New story")


@app.get("/stories/<int:story_id>")
def show_story(story_id):
    story = db.session.get(Story, story_id)
    if story is None:
        abort(404)
    return render_template("detail.html", story=story)


@app.route("/stories/<int:story_id>/edit", methods=["GET", "POST"])
def edit_story(story_id):
    story = db.session.get(Story, story_id)
    if story is None:
        abort(404)
    if request.method == "POST":
        values, error = form_values()
        if error:
            return render_template("form.html", story=values, error=error,
                                   heading="Edit story"), 400
        story.title = values["title"]
        story.author = values["author"]
        story.body = values["body"]
        db.session.commit()  # The session tracks changes to this loaded object.
        flash("Story updated.")
        return redirect(url_for("show_story", story_id=story_id))
    return render_template("form.html", story=story, heading="Edit story")


@app.post("/stories/<int:story_id>/delete")
def delete_story(story_id):
    story = db.session.get(Story, story_id)
    if story is None:
        abort(404)
    db.session.delete(story)
    db.session.commit()
    flash("Story deleted.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
