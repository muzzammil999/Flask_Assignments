import os
import random
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv
from flask import Flask,flash, jsonify, redirect, render_template, request, url_for
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


def get_student(student_id):
    connection = get_db()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        if student:
            student["skills"] = student["skills"].split(",")
        return student
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_student(student_id, student):
    connection = get_db()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE students SET full_name=%s, email=%s, mobile=%s, dob=%s, "
            "gender=%s, course=%s, qualification=%s, training_mode=%s, "
            "skills=%s, experience=%s, address=%s, website=%s, photo=%s "
            "WHERE id=%s",
            (
                student["full_name"],
                student["email"],
                student["mobile"],
                student["dob"],
                student["gender"],
                student["course"],
                student["qualification"],
                student["training_mode"],
                ",".join(student["skills"]),
                student["experience"],
                student["address"],
                student["website"],
                student["photo"],
                student_id,
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


def delete_student(student_id):
    connection = get_db()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def remove_photo_file(filename):
    """Deletes an uploaded photo from disk (ignores missing files)."""
    if not filename:
        return
    path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(filename))
    if os.path.exists(path):
        os.remove(path)



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


@app.route("/students/<int:student_id>/edit", methods=["GET"])
def edit_page(student_id):
    """Shows the registration form pre-filled with the student's details."""
    try:
        student = get_student(student_id)
    except mysql.connector.Error as err:
        print("MySQL error:", err)
        return f"Database error: {err.msg}", 500
    if not student:
        return "Student not found.", 404
    return render_template("register.html", form={}, student=student)



def db_error_response(err):
    print("MySQL error:", err)
    return jsonify({"error": "Database error occurred."}), 500


@app.route("/students/<int:student_id>/update", methods=["POST"])
def update(student_id):
    """Saves the edited student details (called via fetch()/JS)."""
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

    required = [full_name, email, mobile, dob, gender, course,
                qualification, training_mode, address]
    if not all(required):
        return jsonify({"error": "Please fill in all required fields."}), 400
    if not skills:
        return jsonify({"error": "Please select at least one skill."}), 400

    try:
        experience_value = int(experience) if experience else 0
        if experience_value < 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Years of experience must be a non-negative number."}), 400

    try:
        existing = get_student(student_id)
    except mysql.connector.Error as err:
        return db_error_response(err)
    if not existing:
        return jsonify({"error": "Student not found."}), 404

    old_photo = existing["photo"]
    photo_filename = old_photo
    new_photo_path = None

    # Optional: remove the current photo
    if form.get("remove_photo"):
        photo_filename = None

    # Optional: replace the photo
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
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        photo_filename = f"{stamp}-{random.randint(100, 1000)}.{ext}"
        new_photo_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(photo_filename))
        photo.save(new_photo_path)

    try:
        update_student(
            student_id,
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
            },
        )
    except mysql.connector.Error as err:
        if new_photo_path and os.path.exists(new_photo_path):
            os.remove(new_photo_path)
        return db_error_response(err)

    # Update worked: the old photo file is no longer needed.
    if old_photo and old_photo != photo_filename:
        remove_photo_file(old_photo)

    return jsonify({"redirect_url": url_for("student_list")})


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete(student_id):
    """Deletes a student and their photo."""
    try:
        student = get_student(student_id)
        if student:
            delete_student(student_id)
            remove_photo_file(student["photo"])
    except mysql.connector.Error as err:
        print("MySQL error:", err)
        return f"Database error: {err.msg}", 500
    return redirect(url_for("student_list"))


if __name__ == "__main__":
    app.run(debug=True)