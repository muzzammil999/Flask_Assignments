-- =============================================================================
-- Trip Planner database schema (MySQL 8.0.16+ recommended for CHECK constraints)
-- Run this in MySQL Workbench / the mysql CLI, OR just run `python app.py`,
-- which creates/upgrades the same structure automatically (initialize_database()
-- in app.py).  Safe to run more than once.
--
-- Relationships:   users 1 ---- * trips 1 ---- * activities
-- Deleting a user removes their trips; deleting a trip removes its activities.
-- =============================================================================
CREATE DATABASE IF NOT EXISTS trip_planner_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE trip_planner_db;

-- Accounts. Only a salted password HASH is stored (never the password).
-- Written by register(), read by login().
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,          -- UNIQUE also stops duplicate sign-ups
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- A user's trip. image_filename points to a file in the app's uploads/ folder
-- (served by the media route); NULL means "no photo".
-- Written by create_trip()/edit_trip(); read by my_trips(), trip_detail(),
-- completed_trips(). 
CREATE TABLE IF NOT EXISTS trips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,                         -- -> users.id
    destination VARCHAR(160) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    budget DECIMAL(12,2) NOT NULL,                 -- exact money type, never FLOAT
    image_filename VARCHAR(80) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_trips_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_trip_budget CHECK (budget >= 0),
    CONSTRAINT chk_trip_dates CHECK (end_date >= start_date)
) ENGINE=InnoDB;

-- One planned activity inside a trip. `date` and `time` are quoted because they
-- are also MySQL type names. The activity date must fall inside the trip's
-- dates (enforced by the app in validate_activity_form()).
-- Written by add_activity()/edit_activity()/delete_activity().
CREATE TABLE IF NOT EXISTS activities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trip_id INT NOT NULL,                          -- -> trips.id
    name VARCHAR(160) NOT NULL,
    `date` DATE NOT NULL,
    `time` TIME NOT NULL,
    category VARCHAR(40) NOT NULL,                 -- one of CATEGORIES in app.py
    place VARCHAR(200) NOT NULL,
    cost DECIMAL(12,2) NOT NULL,
    image_filename VARCHAR(80) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_activities_trip FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
    CONSTRAINT chk_activity_cost CHECK (cost >= 0),
    INDEX idx_activities_trip_date (trip_id, `date`)  -- fast "activities of a trip by date"
) ENGINE=InnoDB;

-- "Completed trips" are NOT stored - they are computed on the fly (see
-- completed_trips() in app.py): end_date < today, at least one activity, and
-- SUM(activities.cost) <= trips.budget.
