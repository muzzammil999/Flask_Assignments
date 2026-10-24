-- =============================================================================
-- schema.sql - THE DATABASE TABLE DEFINITIONS (reference)
-- =============================================================================
-- WHAT THIS IS
--   The plain-SQL description of the three tables the app uses. It is the
--   "blueprint" of the database.
--
-- DO I HAVE TO RUN IT?
--   No. models.py describes the very same tables in Python, and app.py calls
--   db.create_all() on start-up, which builds them for you. This file exists so
--   you can READ the structure in plain SQL (or run it by hand):
--       sqlite3 trip_planner.db < schema.sql
--   It is safe to run more than once (IF NOT EXISTS).
--
-- RELATIONSHIPS
--       users 1 ----- * trips 1 ----- * activities
--   One user owns many trips; one trip contains many activities.
--   Deleting a trip deletes its activities; deleting a user deletes their trips.
--
-- KEY TERMS
--   Table        a grid of data: columns = fields, rows = records.
--   PRIMARY KEY  the unique id of a row (here: id, 1, 2, 3 ...).
--   FOREIGN KEY  a column that points to a row in ANOTHER table
--                (trips.owner_id -> users.id). It links the tables together.
--   UNIQUE       no two rows may share this value (no duplicate usernames).
--   CHECK        a rule the database enforces itself (budget can't be negative).
--   INDEX        a lookup shortcut, like the index at the back of a book.
--
-- NOTE ON MYSQL: this file is written for SQLite (the default). For MySQL change
--   INTEGER PRIMARY KEY AUTOINCREMENT -> INT AUTO_INCREMENT PRIMARY KEY,
--   TEXT -> VARCHAR(n), and add "ENGINE=InnoDB" -- or simply let db.create_all()
--   do it, which handles every database automatically.
-- =============================================================================

-- Make SQLite enforce FOREIGN KEY rules (it ignores them unless asked).
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- users: one row per registered account.
-- Only a salted password HASH is stored, never the real password.
-- Written by User.register(), read by User.find_by_username() (models.py).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER      NOT NULL PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- trips: one row per trip. image_filename names a file in the uploads/ folder
-- (NULL = no photo).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trips (
    id             INTEGER        NOT NULL PRIMARY KEY AUTOINCREMENT,
    owner_id       INTEGER        NOT NULL,            -- -> users.id
    destination    VARCHAR(160)   NOT NULL,
    start_date     DATE           NOT NULL,
    end_date       DATE           NOT NULL,
    budget         NUMERIC(12, 2) NOT NULL,            -- money, 2 decimals
    image_filename VARCHAR(80),
    created_at     DATETIME       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_trips_owner FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT chk_trip_budget CHECK (budget >= 0),
    CONSTRAINT chk_trip_dates  CHECK (end_date >= start_date)
);

-- ----------------------------------------------------------------------------
-- activities: one row per planned activity inside a trip.
-- The activity date must lie inside the trip's dates (the app checks this in
-- Activity.validate()).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activities (
    id             INTEGER        NOT NULL PRIMARY KEY AUTOINCREMENT,
    trip_id        INTEGER        NOT NULL,            -- -> trips.id
    name           VARCHAR(160)   NOT NULL,
    activity_date  DATE           NOT NULL,
    activity_time  TIME           NOT NULL,
    category       VARCHAR(40)    NOT NULL,            -- one of Config.CATEGORIES
    place          VARCHAR(200)   NOT NULL,
    cost           NUMERIC(12, 2) NOT NULL,
    image_filename VARCHAR(80),
    created_at     DATETIME       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_activities_trip FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    CONSTRAINT chk_activity_cost CHECK (cost >= 0)
);

-- Fast "all activities of one trip, ordered by day".
CREATE INDEX IF NOT EXISTS idx_activities_trip_date ON activities (trip_id, activity_date);

-- "Completed trips" are NOT stored. They are worked out on the fly:
-- a trip is completed when end_date < today (see Trip.completed_for in models.py).
