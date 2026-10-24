-- Run this once in MySQL before either app. Both apps use this same table.
CREATE DATABASE IF NOT EXISTS story_orm_lesson
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE story_orm_lesson;
CREATE TABLE IF NOT EXISTS stories (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  author VARCHAR(80) NOT NULL,
  body TEXT NOT NULL
);
