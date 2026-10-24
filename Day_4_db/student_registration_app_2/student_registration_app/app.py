import os
import random
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, url_for
from werkzeug.utils import secure_filename

# Read database settings from the .env file.
load_dotenv()
app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_PHOTO_SIZE = 2 * 1024 * 1024  # 2 MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    # Opens a connection to MySQL using the values in the .env file.
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
    )


def save_student(student):
    connection = get_db()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO students (full_name, email, mobile, dob, gender, course, "
            "qualification, training_mode, skills, experience, address, website, "
            "photo) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                student["full_name"],
                student["email"],
                student["mobile"],
                student["dob"],
                student["gender"],
                student["course"],
                student["qualification"],
                student["training_mode"],
                ",".join(student["skills"]),  # list -> "HTML,CSS"
                student["experience"],
                student["address"],
                student["website"],
                student["photo"],  # only the image file name is stored
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def all_students():
    connection = get_db()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students ORDER BY id DESC")
        students = cursor.fetchall()
        for student in students:
            # "HTML,CSS" -> ["HTML", "CSS"] so the template works unchanged.
            student["skills"] = student["skills"].split(",")
        return students
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


@app.route("/", methods=["GET"])
def register_page():
    """Shows the registration form."""
    return render_template("register.html", form={})


@app.route("/register", methods=["POST"])
def register():
    """Handles the registration form submitted via fetch()/JS."""
    form = request.form

    full_name = form.get("full_name", "").strip()
    email = form.get("email", "").strip()
    mobile = form.get("mobile", "").strip()
    dob = form.get("dob", "").strip()
    gender = form.get("gender", "").strip()
    course = form.get("course", "").strip()
    qualification = form.get("qualification", "").strip()
    training_mode = form.get("training_mode", "").strip()
    skills = form.getlist("skills")
    experience = form.get("experience", "").strip()
    address = form.get("address", "").strip()
    website = form.get("website", "").strip()
    password = form.get("password", "")
    confirm_password = form.get("confirm_password", "")
    agree = form.get("agree")

    # --- Required-field validation (mirrors the required fields in the form) ---
    required = {
        "full_name": full_name,
        "email": email,
        "mobile": mobile,
        "dob": dob,
        "gender": gender,
        "course": course,
        "qualification": qualification,
        "training_mode": training_mode,
        "address": address,
        "password": password,
        "confirm_password": confirm_password,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        return jsonify({"error": "Please fill in all required fields."}), 400

    if not skills:
        return jsonify({"error": "Please select at least one skill."}), 400

    if not agree:
        return jsonify({"error": "You must agree to register."}), 400

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    try:
        experience_value = int(experience) if experience else 0
        if experience_value < 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Years of experience must be a non-negative number."}), 400

    # --- Optional photo upload ---
    photo_filename = None
    photo_path = None
    photo = request.files.get("photo")
    if photo and photo.filename:
        if not allowed_photo(photo.filename):
            return jsonify({"error": "Photo must be a JPEG or PNG file."}), 400

        photo.seek(0, os.SEEK_END)
        size = photo.tell()
        photo.seek(0)
        if size > MAX_PHOTO_SIZE:
            return jsonify({"error": "Photo size must be under 2 MB."}), 400

        ext = photo.filename.rsplit(".", 1)[1].lower()
        date = datetime.now().strftime("%Y%m%d")
        time = datetime.now().strftime("%H%M%S")
        number = random.randint(100, 1000)
        photo_filename = f"{date}-{time}-{number}.{ext}"
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(photo_filename))
        photo.save(photo_path)

    # --- Save to MySQL (errors are returned as JSON so the page shows them) ---
    try:
        save_student(
            {
                "full_name": full_name,
                "email": email,
                "mobile": mobile,
                "dob": dob,
                "gender": gender,
                "course": course,
                "qualification": qualification,
                "training_mode": training_mode,
                "skills": skills,
                "experience": experience_value,
                "address": address,
                "website": website,
                "photo": photo_filename,
            }
        )
    except mysql.connector.Error as err:
        print("MySQL error:", err)  # full details in the terminal
        # Don't keep an image for a record that was not saved.
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)

        if err.errno == 1062:
            message = "This email is already registered."
        elif err.errno in (1045, 1049, 2003, 2005):
            message = f"Database connection problem: {err.msg}. Check your .env file."
        elif err.errno in (1054, 1146, 1364):
            message = f"Database table problem: {err.msg}. Check your students table."
        else:
            message = f"Database error: {err.msg}"
        return jsonify({"error": message}), 500
    except KeyError as err:
        print("Missing .env value:", err)
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return jsonify({"error": f"Missing value {err} in the .env file."}), 500

    return jsonify({"redirect_url": url_for("student_list")})


@app.route("/students", methods=["GET"])
def student_list():
    """Shows every registered student."""
    try:
        students = all_students()
    except mysql.connector.Error as err:
        print("MySQL error:", err)
        return f"Database error: {err.msg}", 500
    except KeyError as err:
        print("Missing .env value:", err)
        return f"Missing value {err} in the .env file.", 500
    return render_template("students.html", students=students)


if __name__ == "__main__":
    app.run(debug=True)