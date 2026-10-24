from flask import Flask, render_template, request, redirect, url_for, flash, abort

app = Flask(__name__)
app.secret_key = "test-key"

# In-memory List Data Structure storing event dictionaries
events_list = [
    {
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
]

# Helper function to find an event from the list by ID
def get_event(event_id):
    for event in events_list:
        if event["id"] == event_id:
            return event
    abort(404)

# --- Routes using the list data structure ---

@app.route('/')
def index():
    return render_template('index.html', events=events_list)

@app.route('/events/new', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        # Generate new ID and build event dictionary
        new_id = len(events_list) + 1
        new_event = {
            "id": new_id,
            "title": request.form.get('title'),
            "category": request.form.get('category'),
            "date": request.form.get('date'),
            "time": request.form.get('time'),
            "venue": request.form.get('venue'),
            "capacity": int(request.form.get('capacity', 0)),
            "booked_seats": 0,
            "email": request.form.get('email'),
            "deadline": request.form.get('deadline'),
            "description": request.form.get('description'),
            "cover_class": ""
        }
        # Append the new event to the list
        events_list.append(new_event)                             
        flash("Event published successfully!", "success")               
        return redirect(url_for('index'))                          

    return render_template('create_event.html')

@app.route('/events/<int:event_id>')
def event_details(event_id):
    event = get_event(event_id)                                             
    return render_template('event_details.html', event=event)                 

@app.route('/events/<int:event_id>/register', methods=['GET', 'POST'])      
def register_event(event_id):
    event = get_event(event_id)
    if request.method == 'POST':
        seats = int(request.form.get('seats', 1))
        available = event['capacity'] - event['booked_seats']
        if seats <= available:
            # Update booked_seats in the list
            event['booked_seats'] += seats
            flash(f"Successfully registered {seats} seat(s)!", "success")
            return redirect(url_for('event_details', event_id=event_id))
        else:
            flash("Sorry, not enough seats available.", "error")

    return render_template('register.html', event=event)

@app.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
def edit_event(event_id):
    event = get_event(event_id)
    if request.method == 'POST':
        # Update event fields in the list
        event['title'] = request.form.get('title')
        event['category'] = request.form.get('category')
        event['date'] = request.form.get('date')
        event['time'] = request.form.get('time')
        event['venue'] = request.form.get('venue')
        event['capacity'] = int(request.form.get('capacity', event['capacity']))
        event['email'] = request.form.get('email')
        event['deadline'] = request.form.get('deadline')
        event['description'] = request.form.get('description')
        flash("Event updated successfully!", "success")
        return redirect(url_for('event_details', event_id=event_id))

    return render_template('edit_event.html', event=event)

@app.route('/events/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    event = get_event(event_id)
    # Remove event from the list
    events_list.remove(event)
    flash(f"Event '{event['title']}' deleted successfully!", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)