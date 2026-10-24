import os
from flask import Flask, jsonify, render_template, request, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure upload directory for optional photo uploads
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# In-memory storage for submitted student registrations
students = []


@app.route("/", methods=["GET"])
def register_page():
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    mobile = request.form.get("mobile", "").strip()
    dob = request.form.get("dob", "").strip()
    gender = request.form.get("gender", "").strip()
    course = request.form.get("course", "").strip()
    qualification = request.form.get("qualification", "").strip()
    training_mode = request.form.get("training_mode", "").strip()
    skills = request.form.getlist("skills")
    experience = request.form.get("experience", "0").strip()
    address = request.form.get("address", "").strip()
    website = request.form.get("website", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    agree = request.form.get("agree")

    # Server-side validation
    if not full_name or not email or not mobile or not dob or not qualification:
        return jsonify({"error": "Please fill in all required fields."}), 400

    if not skills:
        return jsonify({"error": "Please select at least one skill."}), 400

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    if not agree:
        return jsonify({"error": "You must agree to register."}), 400

    # Handle optional photo upload
    photo_filename = None
    photo = request.files.get("photo")
    if photo and photo.filename != "":
        filename = secure_filename(photo.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        photo.save(save_path)
        photo_filename = filename

    student_record = {
        "full_name": full_name,
        "email": email,
        "mobile": mobile,
        "dob": dob,
        "gender": gender,
        "course": course,
        "qualification": qualification,
        "training_mode": training_mode,
        "skills": skills,
        "experience": experience,
        "address": address,
        "website": website,
        "photo": photo_filename,
    }

    students.append(student_record)

    # Return URL of the list page for JS redirect
    return jsonify({"redirect_url": url_for("student_list")}), 200


@app.route("/students", methods=["GET"])
def student_list():
    return render_template("students.html", students=students)


if __name__ == "__main__":
    app.run(debug=True)