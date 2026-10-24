from flask import Flask, render_template

app = Flask(__name__)
app.secret_key = "test-key"

# 1 dummy event so the detail, edit, and register pages have sample data to show
sample_event = {
    "id": 1,
    "title": "Digital Skills Saturday",
    "category": "Workshop",
    "date": "2026-10-05",
    "time": "10:00",
    "venue": "MITRAz Training Centre",
    "capacity": 30,
    "booked_seats": 12,
    "email": "organizer@example.com",
    "deadline": "2026-10-04",
    "description": "A practical introduction to everyday digital skills for local learners.",
    "cover_class": ""
}
events_list = [sample_event]

# --- Minimal Routes to Test Each Template ---

@app.route('/')
def index():
    return render_template('index.html', events=events_list)

@app.route('/events/new', methods=['GET', 'POST'])
def create_event():
    return render_template('create_event.html')

@app.route('/events/<int:event_id>')
def event_details(event_id):
    return render_template('event_details.html', event=sample_event)

@app.route('/events/<int:event_id>/register', methods=['GET', 'POST'])
def register_event(event_id):
    return render_template('register.html', event=sample_event)

@app.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
def edit_event(event_id):
    return render_template('edit_event.html', event=sample_event)

@app.route('/events/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    return "Delete triggered"

if __name__ == '__main__':
    app.run(debug=True)