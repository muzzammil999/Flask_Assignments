"""Server-rendered book shelf application backed by MySQL.

This version uses ordinary Flask forms and Jinja templates. Form submissions
are validated on the server, saved to MySQL, and followed by a redirect.
"""

import os
from contextlib import contextmanager

import mysql.connector
from flask import Flask, abort, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = 'classroom-demo-change-me'
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'Chinna@9999'),
    'database': os.getenv('FLASK_ONLY_DB_NAME', 'flask_books_html'),
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


def valid(form):
    """Validate submitted form fields and return errors plus cleaned values."""
    title = form.get('title', '').strip()
    author = form.get('author', '').strip()
    status = form.get('status', '')
    errors = []
    if not 2 <= len(title) <= 100:
        errors.append('Title needs 2 to 100 characters.')
    if not 2 <= len(author) <= 80:
        errors.append('Author needs 2 to 80 characters.')
    if status not in ('To read', 'Reading', 'Finished'):
        errors.append('Choose a valid status.')
    return errors, (title, author, status)


@app.route('/')
def home():
    """Render the home page with the newest books from MySQL."""
    with connect() as db:
        with db.cursor(dictionary=True) as cursor:
            cursor.execute('SELECT * FROM books ORDER BY id DESC')
            books = cursor.fetchall()
    return render_template('home.html', books=books)


@app.route('/books/new', methods=['GET', 'POST'])
def create():
    """Show the new-book form or validate and save its submitted values."""
    if request.method == 'GET':
        return render_template('form.html', book={}, errors=[], heading='Add a book')
    errors, values = valid(request.form)
    if errors:
        return render_template('form.html', book=request.form, errors=errors, heading='Add a book'), 400
    with connect() as db, db.cursor() as cursor:
        # Placeholders keep user input separate from SQL command text.
        cursor.execute(
            'INSERT INTO books (title, author, status) VALUES (%s, %s, %s)',
            values,
        )
    flash('Book added.', 'success')
    return redirect(url_for('home'))


@app.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
def edit(book_id):
    """Load a book for editing or validate and save its updated values."""
    with connect() as db:
        with db.cursor(dictionary=True) as cursor:
            cursor.execute('SELECT * FROM books WHERE id = %s', (book_id,))
            book = cursor.fetchone()
    if book is None:
        abort(404)
    if request.method == 'GET':
        return render_template('form.html', book=book, errors=[], heading='Edit book')
    errors, values = valid(request.form)
    if errors:
        return render_template('form.html', book=request.form, errors=errors, heading='Edit book'), 400
    with connect() as db, db.cursor() as cursor:
        cursor.execute(
            'UPDATE books SET title = %s, author = %s, status = %s WHERE id = %s',
            (*values, book_id),
        )
    flash('Book updated.', 'success')
    return redirect(url_for('home'))


@app.route('/books/<int:book_id>/delete', methods=['POST'])
def delete(book_id):
    """Delete the selected book and redirect back to the list."""
    with connect() as db, db.cursor() as cursor:
        cursor.execute('DELETE FROM books WHERE id = %s', (book_id,))
    flash('Book deleted.', 'success')
    return redirect(url_for('home'))


# Create the table before Flask starts accepting requests.
setup()


if __name__ == '__main__':
    # The main guard prevents the development server starting when imported.
    app.run(debug=True, port=5000)
