"""Start the app WITH the new Community Events feature.

Your app.py is unchanged: this file imports it, adds the events blueprint, and runs it.
    python run_events.py
Student pages stay at  /  and  /students ;  events live under  /events
"""
from app import app
from events import bp

app.register_blueprint(bp)

if __name__ == "__main__":
    app.run(debug=True)
