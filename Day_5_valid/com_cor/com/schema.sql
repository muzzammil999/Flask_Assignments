CREATE DATABASE IF NOT EXISTS community_events;
USE community_events;

CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    event_date DATE NOT NULL,
    start_time TIME NOT NULL,
    venue VARCHAR(255) NOT NULL,
    seat_capacity INT NOT NULL,
    organizer_email VARCHAR(150) NOT NULL,
    registration_deadline DATE NOT NULL,
    description TEXT NOT NULL,
    image_filename VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL,
    mobile VARCHAR(20) NOT NULL,
    seats_requested INT NOT NULL DEFAULT 1,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_event_email (event_id, email),
    CONSTRAINT fk_registration_event
        FOREIGN KEY (event_id) REFERENCES events(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

INSERT INTO events
(title, category, event_date, start_time, venue, seat_capacity, organizer_email, registration_deadline, description)
SELECT
'Digital Skills Saturday', 'Workshop', '2026-10-05', '10:00:00',
'MITRAz Training Centre', 30, 'organizer@example.com', '2026-10-04',
'A practical introduction to everyday digital skills for local learners.'
WHERE NOT EXISTS (SELECT 1 FROM events);

INSERT INTO events
(title, category, event_date, start_time, venue, seat_capacity, organizer_email, registration_deadline, description)
SELECT
'Village Clean-up Drive', 'Community', '2026-10-08', '08:30:00',
'Main Road, Puttaparthi', 40, 'organizer@example.com', '2026-10-07',
'A community activity focused on keeping the local area clean.'
WHERE NOT EXISTS (SELECT 1 FROM events WHERE title = 'Village Clean-up Drive');

INSERT INTO events
(title, category, event_date, start_time, venue, seat_capacity, organizer_email, registration_deadline, description)
SELECT
'Resume Help Session', 'Career', '2026-10-12', '14:00:00',
'Learning Hall', 25, 'organizer@example.com', '2026-10-11',
'A practical session to improve resumes and prepare for job opportunities.'
WHERE NOT EXISTS (SELECT 1 FROM events WHERE title = 'Resume Help Session');


select * from events;