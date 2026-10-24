from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Welcome to MITRAz Student Help Portal</h1>
    <h2>Available Services:</h2>
    <ol>
        <li><b>Student Information :</b> /students</li>
        <li><b>Course Information</b> : /courses</li>
        <li><b>Faculty Information</b> : /faculty</li>
        <li><b>Batch Information</b> : /batch</li>
        <li><b>Contact Information</b> : /contact</li>
        <li><b>Student Name</b> : /student/name</li>
        <li><b>Batch Status</b> : /batch-status</li>
        <li><b>Course_name</b> : /course/course_name</li>
    </ol>
    """

@app.route("/students")
def students():
    batch_name = "MITRAz IT7"
    number_of_students = 30
    technology = "Full Stack Web Development"
    current_module = "Flask"
    training_mode = "Classroom Training"

    return f"""
        <h1>Student Information</h1>
        <p><b>Batch Name:</b> {batch_name}</p>
        <p><b>Number of Students:</b> {number_of_students}</p>
        <p><b>Technology:</b> {technology}</p>
        <p><b>Current Module:</b> {current_module}</p>
        <p><b>Training Mode:</b> {training_mode}</p>
        """

@app.route("/courses")
def courses():
    courses = ["Python","HTML and CSS","JavaScript","MySQL","Flask"]
    course_list = ""
    for course in courses:
        course_list += f"<li>{course}</li>"
    return f"""
        <h1>MITRAz Courses</h1>
        <ol>
            {course_list}
        </ol>
        """

@app.route("/faculty")
def faculty():
    faculty = {
        "Python": "Muzzammil Kamnoor",
        "Web Development": "Gowtham Reddy",
        "Database": "Surya Prakash"
         }

    return f"""
        <h1>Faculty Information</h1>
        <p><b>Python Trainer:</b> {faculty["Python"]}</p>
        <p><b>Web Development Trainer:</b> {faculty["Web Development"]}</p>
        <p><b>Database Trainer:</b> {faculty["Database"]}</p>
        """


@app.route("/batch")
def batch():
    batch_name = "MITRAz IT7"
    start_date = "01-July-2026"
    duration = "6 Months"
    number_of_students = 30
    current_technology = "Flask"
    return f"""
        <h1>Batch Information</h1>
        <p><b>Batch Name:</b> {batch_name}</p>
        <p><b>Start Date:</b> {start_date}</p>
        <p><b>Duration:</b> {duration}</p>
        <p><b>Number of Students:</b> {number_of_students}</p>
        <p><b>Current Technology:</b> {current_technology}</p>
    """


@app.route("/contact")
def contact():
    return """
        <h1>MITRAz Contact Information</h1>
        <p><b>Email:</b> support@mitraz.example</p>
        <p><b>Phone:</b> +91 98765 43210</p>
        <p><b>Address:</b> MITRAz Learning Hub, Hyderabad</p>
        <p><b>Working Hours:</b> Monday - Saturday, 9:00 AM - 6:00 PM</p>
        """



@app.route("/student/<name>")
def student(name):
   
    return f"""
    <h1>Student Portal</h1>
    <p>Welcome {name.capitalize()}!</p>
    <p>You are viewing the MI5TRAz Student Portal.</p>
    """

@app.route("/course/<course_name>")
def course(course_name):
    return f"""
            <h1>Course Information</h1>
            <p>You selected the course: <b>{course_name.capitalize()}</b></p>
            """


@app.route("/batch-status")
def batch_status():
    total_students=30
    completed_students=24
    percentage=(completed_students/total_students)*100
    if percentage>=80:
        status="Batch is progressing well"
    elif percentage>=50:
        status="Batch is making progress"
    else:
        status="Batch needs improvement"
    return f"""
        <h1>Batch Status</h1>
        <p><b>Total Students:</b> {total_students}</p>
        <p><b>Completed Students:</b> {completed_students}</p>
        <p><b>Completion Percentage:</b> {percentage:.2f}%</p>
        <p><b>Status:</b> {status}</p>
        """

if __name__ == "__main__":
    app.run(debug=True)