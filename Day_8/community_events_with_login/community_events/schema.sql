-- =====================================================================
-- Community Event Manager - database setup for MySQL Workbench
-- =====================================================================
-- HOW TO RUN:
--   1. Open MySQL Workbench and connect to your local MySQL server.
--   2. File > Open SQL Script... > choose this file.
--   3. Click the lightning bolt icon (Execute) to run the whole script.
--   4. Press the refresh icon in the SCHEMAS panel to see the new tables.
--
-- SAFE TO RUN AGAIN: every table uses "IF NOT EXISTS" and the sample
-- event is only added when the events table is empty. So if you already
-- have the community_events database, just run this file once more:
-- it ADDS the new "users" table and keeps all your events/registrations.
-- =====================================================================

-- Create the database (only if it does not exist yet) and use it.
CREATE DATABASE IF NOT EXISTS CE1;
USE CE1;

-- ---------------------------------------------------------------------
-- Table 1: events  (one row = one event)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id                    INT AUTO_INCREMENT PRIMARY KEY,  -- unique number, MySQL fills it
    title                 VARCHAR(150) NOT NULL,
    category              VARCHAR(50)  NOT NULL,           -- Workshop / Community / Career
    event_date            DATE         NOT NULL,           -- example: 2026-10-05
    start_time            TIME         NOT NULL,           -- example: 10:00:00
    venue                 VARCHAR(150) NOT NULL,
    seat_capacity         INT          NOT NULL,           -- total seats
    booked_seats          INT          NOT NULL DEFAULT 0, -- seats already taken
    organizer_email       VARCHAR(150) NOT NULL,
    registration_deadline DATE         NOT NULL,
    description           TEXT         NOT NULL,
    image_filename        VARCHAR(100) NULL                -- example: 20261004_104530.jpg
);

-- ---------------------------------------------------------------------
-- Table 2: registrations  (one row = one person registered for an event)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS registrations (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    event_id   INT          NOT NULL,                      -- which event (events.id)
    full_name  VARCHAR(100) NOT NULL,
    email      VARCHAR(150) NOT NULL,
    mobile     VARCHAR(10)  NOT NULL,
    seats      INT          NOT NULL,                      -- 1 or 2
    FOREIGN KEY (event_id) REFERENCES events(id)
);

-- ---------------------------------------------------------------------
-- Table 3 (NEW): users  (one row = one person who can log in)
-- ---------------------------------------------------------------------
-- We NEVER store the real password. password_hash holds a scrambled
-- (hashed) version that cannot be turned back into the password.
-- UNIQUE on username means MySQL itself refuses two accounts with the
-- same name. (MySQL compares names without caring about upper/lower
-- case, so "Priya" and "priya" count as the same name.)
CREATE TABLE IF NOT EXISTS users (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    username       VARCHAR(30)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,                  -- long text made by Werkzeug
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- Sample event (so the home page is not empty)
-- Only inserted when the events table has no rows yet.
-- ---------------------------------------------------------------------
INSERT INTO events
    (title, category, event_date, start_time, venue, seat_capacity,
     booked_seats, organizer_email, registration_deadline, description, image_filename)
SELECT 'Digital Skills Saturday', 'Workshop', '2026-12-05', '10:00:00',
       'MITRAz Training Centre', 30, 12, 'organizer@example.com', '2026-12-01',
       'A practical introduction to everyday digital skills for local learners.', NULL
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM events);

-- Check the data:
SELECT * FROM events;
SELECT id, username, created_at FROM users;
