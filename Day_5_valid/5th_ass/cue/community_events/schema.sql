-- =====================================================================
-- Community Event Manager - database setup for MySQL Workbench
-- =====================================================================
-- HOW TO RUN:
--   1. Open MySQL Workbench and connect to your local MySQL server.
--   2. File > Open SQL Script... > choose this file.
--   3. Click the lightning bolt icon (Execute) to run the whole script.
--   4. Press the refresh icon in the SCHEMAS panel to see the new tables.
-- =====================================================================

-- Create the database (only if it does not exist yet) and use it.
CREATE DATABASE IF NOT EXISTS community_events;
USE community_events;

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
-- Sample event (so the home page is not empty)
-- ---------------------------------------------------------------------
INSERT INTO events
    (title, category, event_date, start_time, venue, seat_capacity,
     booked_seats, organizer_email, registration_deadline, description, image_filename)
VALUES
    ('Digital Skills Saturday', 'Workshop', '2026-12-05', '10:00:00',
     'MITRAz Training Centre', 30, 12, 'organizer@example.com', '2026-12-01',
     'A practical introduction to everyday digital skills for local learners.', NULL);

-- Check the data:
SELECT * FROM events;
