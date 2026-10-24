"""Optional: create the stories table from the ORM model after database creation."""
from app import app, db

with app.app_context():
    db.create_all()  # Creates missing tables; does not migrate existing tables.
print("Missing tables created (if any).")
