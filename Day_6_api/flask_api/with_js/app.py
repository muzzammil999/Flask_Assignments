"""JSON API for a browser-based book shelf, backed by MySQL.

The API validates JSON requests and returns JSON responses with HTTP status
codes that describe the outcome of each CRUD operation.
"""

import os
from contextlib import contextmanager

import mysql.connector
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
STATUSES = ('To read', 'Reading', 'Finished')
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'Chinna@9999'),
    'database': os.getenv('WITH_JS_DB_NAME', 'flask_books_api'),
}


@contextmanager
def connect():
    """Yield a MySQL connection and commit or roll back its transaction."""
    db = mysql.connector.connect(**MYSQL_CONFIG)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def setup():
    """Create the books table when the configured database is first used."""
    with connect() as db:
        with db.cursor() as cursor:
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS books ('
                'id INT AUTO_INCREMENT PRIMARY KEY, '
                'title VARCHAR(100) NOT NULL, '
                'author VARCHAR(80) NOT NULL, '
                'status VARCHAR(20) NOT NULL)'
            )


def validate(data):
    """Validate a decoded JSON object and return errors plus cleaned values."""
    if not isinstance(data, dict):
        return ['Send a JSON object.'], None
    title = str(data.get('title', '')).strip()
    author = str(data.get('author', '')).strip()
    status = data.get('status', '')
    errors = []
    if not 2 <= len(title) <= 100:
        errors.append('Title needs 2 to 100 characters.')
    if not 2 <= len(author) <= 80:
        errors.append('Author needs 2 to 80 characters.')
    if status not in STATUSES:
        errors.append('Choose a valid status.')
    return errors, (title, author, status)


def one(book_id):
    """Return one book as a dictionary, or None when its ID is unknown."""
    with connect() as db:
        with db.cursor(dictionary=True) as cursor:
            cursor.execute('SELECT * FROM books WHERE id = %s', (book_id,))
            return cursor.fetchone()


@app.route('/')
def home():
    """Serve the HTML shell; JavaScript loads and renders the book data."""
    return render_template('index.html')


@app.get('/api/books')
def list_books():
    """Return all books as a JSON array, newest first."""
    with connect() as db:
        with db.cursor(dictionary=True) as cursor:
            cursor.execute('SELECT * FROM books ORDER BY id DESC')
            books = cursor.fetchall()
    return jsonify(books)


@app.get('/api/books/<int:book_id>')
def get_book(book_id):
    """Return one book, using 404 when the requested ID does not exist."""
    book = one(book_id)
    if book is None:
        return jsonify(error='Book not found.'), 404
    return jsonify(book)


@app.post('/api/books')
def create_book():

    """Validate a JSON body, insert its book, and return it with status 201."""
    
    if not request.is_json:
        return jsonify(error='Send JSON with Content-Type: application/json.'), 415
    errors, values = validate(request.get_json(silent=True))
    if errors:
        return jsonify(errors=errors), 400
    with connect() as db, db.cursor() as cursor:
        # Parameterized SQL avoids treating submitted values as SQL syntax.
        cursor.execute(
            'INSERT INTO books (title, author, status) VALUES (%s, %s, %s)',
            values,
        )
        book_id = cursor.lastrowid
    return jsonify(one(book_id)), 201


@app.put('/api/books/<int:book_id>')
def update_book(book_id):
    """Replace a book's fields or return 400/404 for invalid requests."""
    if not request.is_json:
        return jsonify(error='Send JSON with Content-Type: application/json.'), 415
    errors, values = validate(request.get_json(silent=True))
    if errors:
        return jsonify(errors=errors), 400
    with connect() as db:
        with db.cursor() as cursor:
            cursor.execute('SELECT id FROM books WHERE id = %s', (book_id,))
            if cursor.fetchone() is None:
                return jsonify(error='Book not found.'), 404
        with db.cursor() as cursor:
            cursor.execute(
                'UPDATE books SET title = %s, author = %s, status = %s WHERE id = %s',
                (*values, book_id),
            )
    return jsonify(one(book_id))


@app.delete('/api/books/<int:book_id>')
def delete_book(book_id):
    """Delete one book, returning 404 if no row matched the requested ID."""
    with connect() as db, db.cursor() as cursor:
        cursor.execute('DELETE FROM books WHERE id = %s', (book_id,))
        if not cursor.rowcount:
            return jsonify(error='Book not found.'), 404
    # HTTP 204 means the deletion succeeded and there is no response body.
    return '', 204


# Create the table before Flask starts accepting requests.
setup()


if __name__ == '__main__':
    # The main guard prevents the development server starting when imported.
    app.run(debug=True, port=5001)
