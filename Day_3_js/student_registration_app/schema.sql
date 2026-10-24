-- Run this ONCE in MySQL Workbench (or the mysql command line)
CREATE DATABASE IF NOT EXISTS student_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE student_db;

CREATE TABLE IF NOT EXISTS students (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    full_name      VARCHAR(100)  NOT NULL,
    email          VARCHAR(120)  NOT NULL UNIQUE,
    mobile         VARCHAR(20)   NOT NULL,
    dob            DATE          NOT NULL,
    gender         VARCHAR(20)   NOT NULL,
    course         VARCHAR(60)   NOT NULL,
    qualification  VARCHAR(60)   NOT NULL,
    training_mode  VARCHAR(20)   NOT NULL,
    skills         VARCHAR(255)  NOT NULL,      -- e.g. "HTML, CSS, Python"
    experience     INT           NOT NULL DEFAULT 0,
    address        TEXT          NOT NULL,
    website        VARCHAR(255)  NULL,
    photo          MEDIUMBLOB    NULL,          -- the image itself (up to 16 MB)
    photo_type     VARCHAR(30)   NULL,          -- "image/png" or "image/jpeg"
    password_hash  VARCHAR(255)  NOT NULL,
    created_at     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);
