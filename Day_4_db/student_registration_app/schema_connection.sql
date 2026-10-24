CREATE DATABASE IF NOT EXISTS student_db;
USE student_db;


DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    full_name      VARCHAR(100)  NOT NULL,
    email          VARCHAR(120)  NOT NULL UNIQUE,
    mobile         VARCHAR(20)   NOT NULL,
    dob            DATE          NOT NULL,
    gender         VARCHAR(20)   NOT NULL,
    course         VARCHAR(60)   NOT NULL,
    qualification  VARCHAR(60)   NOT NULL,
    training_mode  VARCHAR(20)   NOT NULL,
    skills         VARCHAR(255)  NOT NULL,
    experience     INT           NOT NULL DEFAULT 0,
    address        TEXT          NOT NULL,
    website        VARCHAR(255)  NULL,
    photo          VARCHAR(255)  NULL,
    created_at     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);

SELECT * FROM students;

select full_name FROM students;

