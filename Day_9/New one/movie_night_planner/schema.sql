-- Movie Night Planner: run this file once in MySQL Workbench (MySQL 5.7.8+ / 8.x).
CREATE DATABASE IF NOT EXISTS movie_night_db;
USE movie_night_db;

CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(30)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS movies (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          NOT NULL,            -- who proposed it
    title      VARCHAR(100) NOT NULL,
    genre      VARCHAR(100) NOT NULL,            -- 1 to 3 genres, e.g. 'Sci-Fi,Drama'
    runtime    INT          NOT NULL,            -- minutes
    rating     VARCHAR(10)  NOT NULL,            -- U, U/A, A
    synopsis   VARCHAR(240) NOT NULL,
    poster     VARCHAR(100) NULL,                -- file name inside static/uploads
    likes      JSON         NOT NULL,            -- ids of users who liked it, e.g. '["1","4"]'
    FOREIGN KEY (user_id) REFERENCES users(id)
);
-- There is no likes table: the likes column above holds everything.
