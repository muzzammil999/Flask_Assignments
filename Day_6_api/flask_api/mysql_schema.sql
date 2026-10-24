-- Create the separate databases used by the two classroom applications.
CREATE DATABASE IF NOT EXISTS flask_books_html
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
    

-- CREATE DATABASE IF NOT EXISTS flask_books_api
--     CHARACTER SET utf8mb4
--     COLLATE utf8mb4_unicode_ci;

-- Server-rendered Flask app database.
USE flask_books_html;

CREATE TABLE IF NOT EXISTS books (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    author VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL
    
);

-- JSON API app database.
-- USE flask_books_api;

-- CREATE TABLE IF NOT EXISTS books (
--     id INT AUTO_INCREMENT PRIMARY KEY,
--     title VARCHAR(100) NOT NULL,
--     author VARCHAR(80) NOT NULL,
--     status VARCHAR(20) NOT NULL
-- );



select *from books;