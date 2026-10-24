"""
models.py - THE DATA LAYER (tables as Python classes + all database logic)
=========================================================================

WHAT THIS FILE DOES
    Describes the three database tables as Python classes (User, Trip,
    Activity) and holds every piece of logic that reads, writes or checks data.
    app.py never writes SQL; it just calls the methods defined here, e.g.
        Trip.get_owned(5, user_id)      or      trip.save()

WHY IT IS A SEPARATE FILE
    "Separation of concerns": app.py decides WHAT to show, models.py knows HOW
    the data is stored and validated. You can change one without touching the
    other.

--------------------------------------------------------------------------
KEY TERMS USED IN THIS FILE
--------------------------------------------------------------------------
ORM  (Object-Relational Mapper)
    A translator between Python objects and database rows. Instead of writing
        INSERT INTO trips (destination, ...) VALUES ('Goa', ...)
    you write
        Trip(destination='Goa', ...).save()
    Analogy: a human interpreter. You speak Python, the database speaks SQL,
    the ORM translates in both directions. Here the ORM is SQLAlchemy, wrapped
    by Flask-SQLAlchemy.

Model
    A Python class that represents ONE table. The class = the table, each
    attribute = a column, and each object (instance) = one row.
    Analogy: a blank paper form (class) versus a filled-in form (object).

db.session  (the "Session")
    A shopping basket of pending changes. `db.session.add(obj)` puts a change in
    the basket; `db.session.commit()` pays for everything at once (saves it
    permanently); `db.session.rollback()` empties the basket if something broke.

Database connection / Cursor
    A *connection* is the open phone line to the database; a *cursor* is the
    pointer that walks through the rows of a query result, like your finger
    following a line of text. In the old way of working you managed both by
    hand. Here SQLAlchemy opens the connection and drives the cursor for you,
    so you never see them. Look at config.py for the connection address.

Query
    A question asked to the database: "give me all trips where owner_id = 3".
    Written with the ORM as   Trip.query.filter_by(owner_id=3).all()

Relationship
    A Python shortcut across a foreign key: `trip.activities` gives the list of
    that trip's activities, and `activity.trip` gives the trip back.

Validation
    Checking user input BEFORE saving it (is the date real? is the budget a
    number?). Never trust what a browser sends.

Hashing (passwords)
    A one-way scramble. We store scramble(password), never the password, so even
    someone who steals the database cannot read passwords.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config

# `db` is THE gateway to the database. It is created here, empty, and connected
# to the Flask app in app.py with db.init_app(app). Every model below inherits
# from db.Model, which is what turns a plain class into a table definition.
db = SQLAlchemy()

# Largest amount that fits the NUMERIC(12,2) money columns.
MAX_MONEY = Decimal("9999999999.99")


# =============================================================================
# SMALL SHARED HELPERS
# =============================================================================
class SaveMixin:
    """Gives every model a `save()` and `delete()` method.

    A "mixin" is a small class you inherit from to borrow ready-made methods.
    Both models that need these methods list it as a parent class.
    """

    def save(self):
        """INSERT (new object) or UPDATE (changed object) and make it permanent."""
        try:
            db.session.add(self)      # put the change in the basket
            db.session.commit()       # pay: write it to the database
        except Exception:
            db.session.rollback()     # something failed -> empty the basket, keep DB clean
            raise                     # let the error continue so it is not hidden

    def delete(self):
        """DELETE this row from the database."""
        try:
            db.session.delete(self)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


def parse_money(raw):
    """Turn what a user typed ("12.5") into a Decimal rounded to 2 places.

    Raises InvalidOperation if it is blank, not a number, negative or too big.
    Decimal (not float) is used because float can't represent 0.1 exactly,
    which matters for money.
    """
    amount = Decimal((raw or "").strip())
    if not amount.is_finite() or amount < 0 or amount > MAX_MONEY:
        raise InvalidOperation
    return amount.quantize(Decimal("0.01"))


def parse_date(raw):
    """Turn "2026-12-31" into a date object, or return None if it is invalid."""
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def parse_time(raw):
    """Turn "14:30" (or "14:30:00") into a time object, or None if invalid."""
    for fmt in ("%H:%M", "%H:%M:%S"):   # browsers send HH:MM, sometimes HH:MM:SS
        try:
            return datetime.strptime(raw, fmt).time()
        except (ValueError, TypeError):
            continue
    return None


# =============================================================================
# MODEL 1: USER  ->  table `users`
# =============================================================================
class User(SaveMixin, db.Model):
    """One registered account."""

    __tablename__ = "users"          # the real table name in the database

    # --- columns (same as schema.sql) ---
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())

    # --- relationship: user.trips = every trip this user owns ---
    # cascade="all, delete-orphan": deleting a user also deletes their trips.
    trips = db.relationship("Trip", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"

    # ---------------------------- data logic ----------------------------
    @classmethod
    def find_by_username(cls, username):
        """Return the User with this username, or None. (Used by login/register.)"""
        return cls.query.filter_by(username=username).first()

    @classmethod
    def validate_registration(cls, username, password, confirm):
        """Check the sign-up form. Returns a dict {field_name: error_message}.
        An empty dict means everything is fine."""
        errors = {}
        if not username:
            errors["username"] = "Username is required."
        elif len(username) > 80:
            errors["username"] = "Username must be 80 characters or fewer."
        elif cls.find_by_username(username):
            errors["username"] = "That username is already registered."
        if len(password) < 8:
            errors["password"] = "Password must contain at least 8 characters."
        if password != confirm:
            errors["confirm_password"] = "Passwords do not match."
        return errors

    @classmethod
    def register(cls, username, password):
        """Create and save a new user. The password is hashed first, so the
        plain password is never stored anywhere."""
        user = cls(username=username, password_hash=generate_password_hash(password))
        user.save()
        return user

    def check_password(self, password):
        """True if `password` matches the stored hash (used at login)."""
        return check_password_hash(self.password_hash, password)


# =============================================================================
# MODEL 2: TRIP  ->  table `trips`
# =============================================================================
class Trip(SaveMixin, db.Model):
    """One trip: destination, dates, budget and an optional photo."""

    __tablename__ = "trips"
    # Rules the database itself enforces (also written in schema.sql).
    __table_args__ = (
        CheckConstraint("budget >= 0", name="chk_trip_budget"),
        CheckConstraint("end_date >= start_date", name="chk_trip_dates"),
    )

    # --- columns ---
    id = db.Column(db.Integer, primary_key=True)
    # ForeignKey = "this number is the id of a row in the users table".
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    destination = db.Column(db.String(160), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    budget = db.Column(db.Numeric(12, 2), nullable=False)
    image_filename = db.Column(db.String(80), nullable=True)   # file inside uploads/
    created_at = db.Column(db.DateTime, server_default=func.now())

    # --- relationships ---
    owner = db.relationship("User", back_populates="trips")
    # trip.activities is always sorted: by day, then time of day, then id.
    activities = db.relationship(
        "Activity", back_populates="trip", cascade="all, delete-orphan",
        order_by=lambda: (Activity.activity_date, Activity.activity_time, Activity.id),
    )

    def __repr__(self):
        return f"<Trip {self.destination}>"

    # ------------------- computed values (no extra columns) -------------------
    # @property lets you write `trip.total_cost` (no parentheses) as if it were
    # a column, but the value is calculated fresh each time from saved rows.
    @property
    def total_cost(self):
        """Sum of the cost of all activities in this trip."""
        return sum((a.cost for a in self.activities), Decimal("0"))

    @property
    def activity_count(self):
        """How many activities this trip has."""
        return len(self.activities)

    @property
    def remaining(self):
        """Budget minus total cost. A NEGATIVE number means over budget."""
        return self.budget - self.total_cost

    @property
    def is_completed(self):
        """A trip is 'completed' once its end date is before today."""
        return self.end_date < date.today()

    def activities_by_day(self):
        """Group activities for display: {date: [activity, activity, ...]}.
        Because trip.activities is already sorted, the dict is in date order."""
        grouped = {}
        for activity in self.activities:
            grouped.setdefault(activity.activity_date, []).append(activity)
        return grouped

    def first_activity_outside(self, start, end):
        """Return the first activity that would fall outside start..end, else None.
        Used to stop a user from shrinking trip dates past an existing activity."""
        for activity in self.activities:
            if activity.activity_date < start or activity.activity_date > end:
                return activity
        return None

    def form_values(self):
        """This trip's data as strings, ready to pre-fill the edit form."""
        return {
            "destination": self.destination,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "budget": self.budget,
        }

    # ------------------------------ queries ------------------------------
    @classmethod
    def get_owned(cls, trip_id, user_id):
        """Return the trip only if it belongs to this user, else None.
        This single check is what keeps users from seeing each other's trips."""
        return cls.query.filter_by(id=trip_id, owner_id=user_id).first()

    @classmethod
    def active_for(cls, user_id):
        """Upcoming or ongoing trips (end date today or later), soonest first."""
        return (cls.query
                .filter(cls.owner_id == user_id, cls.end_date >= date.today())
                .order_by(cls.start_date.asc(), cls.id.desc())
                .all())

    @classmethod
    def completed_for(cls, user_id, search="", limit=None):
        """Finished trips (end date before today), most recent first.

        search: optional text; keeps trips whose destination contains it.
        limit:  optional maximum number of trips to return.
        """
        query = cls.query.filter(cls.owner_id == user_id, cls.end_date < date.today())
        if search:
            # autoescape=True makes "%" and "_" typed by the user match literally.
            query = query.filter(cls.destination.contains(search, autoescape=True))
        query = query.order_by(cls.end_date.desc(), cls.id.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def count_completed(cls, user_id):
        """How many finished trips this user has."""
        return cls.query.filter(cls.owner_id == user_id, cls.end_date < date.today()).count()

    # ---------------------------- validation ----------------------------
    @staticmethod
    def validate(form):
        """Check the create/edit trip form.

        Returns (values, errors):
          values - cleaned data using the model's column names, ready for
                   Trip(**values) or setattr().
          errors - {form_field_name: message}; empty when the input is valid.
        """
        destination = form.get("destination", "").strip()
        start = parse_date(form.get("start_date", ""))
        end = parse_date(form.get("end_date", ""))
        errors = {}

        if not destination:
            errors["destination"] = "Destination is required."
        elif len(destination) > 160:
            errors["destination"] = "Destination must be 160 characters or fewer."
        if start is None:
            errors["start_date"] = "Enter a valid start date."
        if end is None:
            errors["end_date"] = "Enter a valid end date."
        if start and end and end < start:
            errors["end_date"] = "End date must be on or after the start date."
        try:
            budget = parse_money(form.get("budget", ""))
        except (InvalidOperation, ValueError, TypeError):
            budget = None
            errors["budget"] = "Budget must be a number from 0 to 9,999,999,999.99."

        values = {"destination": destination, "start_date": start,
                  "end_date": end, "budget": budget}
        return values, errors

    def apply(self, values):
        """Copy validated values onto this trip (used when editing)."""
        for field, value in values.items():
            setattr(self, field, value)


# =============================================================================
# MODEL 3: ACTIVITY  ->  table `activities`
# =============================================================================
class Activity(SaveMixin, db.Model):
    """One planned activity (a museum visit, a dinner ...) inside a trip."""

    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint("cost >= 0", name="chk_activity_cost"),
        db.Index("idx_activities_trip_date", "trip_id", "activity_date"),
    )

    # --- columns ---
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    activity_date = db.Column(db.Date, nullable=False)
    activity_time = db.Column(db.Time, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    place = db.Column(db.String(200), nullable=False)
    cost = db.Column(db.Numeric(12, 2), nullable=False)
    image_filename = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())

    # --- relationship: activity.trip = the trip this activity belongs to ---
    trip = db.relationship("Trip", back_populates="activities")

    def __repr__(self):
        return f"<Activity {self.name}>"

    # ------------------------------ queries ------------------------------
    @classmethod
    def get_owned(cls, activity_id, user_id):
        """Return the activity only if its TRIP belongs to this user, else None.
        (JOIN = look up the activity's trip row in the same query.)"""
        return (cls.query.join(Trip, Trip.id == cls.trip_id)
                .filter(cls.id == activity_id, Trip.owner_id == user_id)
                .first())

    def form_values(self):
        """This activity's data as strings, ready to pre-fill the edit form.
        (Form field names are 'date' and 'time'; the columns are activity_*.)"""
        return {
            "name": self.name,
            "date": self.activity_date.isoformat(),
            "time": self.activity_time.strftime("%H:%M"),
            "category": self.category,
            "place": self.place,
            "cost": self.cost,
        }

    # ---------------------------- validation ----------------------------
    @staticmethod
    def validate(form, trip):
        """Check the add/edit activity form.

        `trip` is the parent Trip: the activity date must fall inside its dates.
        Returns (values, errors) just like Trip.validate().
        """
        name = form.get("name", "").strip()
        place = form.get("place", "").strip()
        category = form.get("category", "").strip()
        errors = {}

        # Required text fields and their maximum lengths (match the columns).
        for field, text, limit in (("name", name, 160), ("place", place, 200)):
            if not text:
                errors[field] = f"{field.capitalize()} is required."
            elif len(text) > limit:
                errors[field] = f"{field.capitalize()} must be {limit} characters or fewer."
        if category not in Config.CATEGORIES:
            errors["category"] = "Choose a category from the list."

        when = parse_date(form.get("date", ""))
        if when is None:
            errors["date"] = "Enter a valid activity date."
        elif not trip.start_date <= when <= trip.end_date:
            errors["date"] = "Activity date must be within the trip dates."

        at = parse_time(form.get("time", ""))
        if at is None:
            errors["time"] = "Enter a valid time."

        try:
            cost = parse_money(form.get("cost", ""))
        except (InvalidOperation, ValueError, TypeError):
            cost = None
            errors["cost"] = "Estimated cost must be a number from 0 to 9,999,999,999.99."

        values = {"name": name, "activity_date": when, "activity_time": at,
                  "category": category, "place": place, "cost": cost}
        return values, errors

    def apply(self, values):
        """Copy validated values onto this activity (used when editing)."""
        for field, value in values.items():
            setattr(self, field, value)


# =============================================================================
# PHOTO OWNERSHIP CHECK
# =============================================================================
def image_belongs_to_user(filename, user_id):
    """True if `filename` is the photo of a trip or activity owned by this user.
    Used by the /media route so one user cannot open another user's photos."""
    on_trip = Trip.query.filter_by(image_filename=filename, owner_id=user_id).first()
    if on_trip:
        return True
    on_activity = (Activity.query.join(Trip, Trip.id == Activity.trip_id)
                   .filter(Activity.image_filename == filename, Trip.owner_id == user_id)
                   .first())
    return on_activity is not None
