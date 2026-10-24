# app.py

from flask import Flask, render_template, request, jsonify
from config import Config
from models import db, Student

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return render_template("form.html")


@app.route("/add-student", methods=["POST"])
def add_student():
    data = request.get_json()

    name = data.get("name")
    age = data.get("age")
    email = data.get("email")

    new_student = Student(
        name=name,
        age=age,
        email=email,
        
    )

    db.session.add(new_student)
    db.session.commit()

    return jsonify({"message": "Student added successfully!"})


if __name__ == "__main__":
    app.run(debug=True)