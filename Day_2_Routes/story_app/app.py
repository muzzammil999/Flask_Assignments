from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)
stories = []

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        story = request.form.get("story", "").strip()

        if title and author and story:
            stories.append({
                "title": title,
                "author": author,
                "story": story,
            })
        return redirect(url_for("home"))

    return render_template("home.html", stories=stories)


@app.route("/edit/<int:story_id>", methods=["GET", "POST"])
def edit_story(story_id):
    if story_id >= len(stories):
        return "Story not found", 404

    story = stories[story_id]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        story_text = request.form.get("story", "").strip()

        if title and author and story_text:
            story.update({
                "title": title,
                "author": author,
                "story": story_text,
            })
            return redirect(url_for("home"))
        return render_template("edit_story.html", form=request.form, error="Please fill in all fields.")
    return render_template("edit_story.html", form=story)


@app.route("/delete/<int:story_id>", methods=["GET", "POST"])
def delete_story(story_id):
    if story_id >= len(stories):
        return "Story not found", 404
    stories.pop(story_id)
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
