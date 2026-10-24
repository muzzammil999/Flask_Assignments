CREATE DATABASE IF NOT EXISTS student_registration;
USE student_registration;

CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    mobile VARCHAR(20) NOT NULL,
    dob DATE NOT NULL,
    gender VARCHAR(20) NOT NULL,
    course VARCHAR(100) NOT NULL,
    qualification VARCHAR(100) NOT NULL,
    training_mode VARCHAR(20) NOT NULL,
    skills VARCHAR(255) NOT NULL,
    experience INT NOT NULL DEFAULT 0,
    address TEXT NOT NULL,
    website VARCHAR(255),
    photo VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL
);
