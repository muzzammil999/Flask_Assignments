-- NEW tables for the Community Event Manager (your students table is not touched).
-- Run against the same database as your .env:   mysql -u root -p student_db < events_schema.sql

CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    category VARCHAR(30) NOT NULL,
    event_date DATE NOT NULL,
    start_time TIME NOT NULL,
    venue VARCHAR(150) NOT NULL,
    capacity INT NOT NULL,
    organizer_email VARCHAR(100) NOT NULL,
    reg_deadline DATE NOT NULL,
    description TEXT NOT NULL,
    image VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    mobile VARCHAR(20) NOT NULL,
    seats TINYINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY one_per_event (event_id, email),      -- same email can register once per event
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);
