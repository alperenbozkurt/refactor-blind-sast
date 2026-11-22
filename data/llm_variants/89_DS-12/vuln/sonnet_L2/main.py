from hashlib import md5

import sqlite3
from flask import Flask, request, render_template, redirect, url_for, session

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATABASE_PATH = 'books.db'
SECRET_KEY = 'supersecretkey'
DEBUG_MODE = True

DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'
DEFAULT_BOOK = ('The Great Gatsby', 'F. Scott Fitzgerald')

SESSION_USER_KEY = 'user_id'
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'
HTTP_UNAUTHORIZED = 401

# --------------------------------------------------------------------------- #
# SQL statements
# --------------------------------------------------------------------------- #
CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users '
    '(id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
)
CREATE_BOOKS_TABLE = (
    'CREATE TABLE IF NOT EXISTS books '
    '(id INTEGER PRIMARY KEY, title TEXT, author TEXT)'
)
CREATE_REVIEWS_TABLE = (
    'CREATE TABLE IF NOT EXISTS reviews '
    '(id INTEGER PRIMARY KEY, book_id INTEGER, user_id INTEGER, review TEXT)'
)
SCHEMA_STATEMENTS = (CREATE_USERS_TABLE, CREATE_BOOKS_TABLE, CREATE_REVIEWS_TABLE)

COUNT_USERS = 'SELECT COUNT(*) FROM users'
INSERT_USER = 'INSERT INTO users (username, password) VALUES (?, ?)'
INSERT_BOOK = 'INSERT INTO books (title, author) VALUES (?, ?)'
INSERT_REVIEW = 'INSERT INTO reviews (book_id, user_id, review) VALUES (?, ?, ?)'

SELECT_ALL_BOOKS = 'SELECT * FROM books'
SELECT_ALL_REVIEWS = '''
    SELECT reviews.id, books.title, users.username, reviews.review
    FROM reviews
    JOIN books ON reviews.book_id = books.id
    JOIN users ON reviews.user_id = users.id
'''
SELECT_USER_BY_CREDENTIALS = 'SELECT * FROM users WHERE username = ? AND password = ?'
SEARCH_BOOKS = 'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?'

# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.secret_key = SECRET_KEY


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def hash_password(password):
    # NOTE: MD5 is kept for compatibility with existing stored password hashes.
    return md5(password.encode()).hexdigest()


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(cursor):
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)


def _seed_defaults(conn, cursor):
    cursor.execute(COUNT_USERS)
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            INSERT_USER,
            (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD)),
        )
        cursor.execute(INSERT_BOOK, DEFAULT_BOOK)
        conn.commit()


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    _create_schema(cursor)
    _seed_defaults(conn, cursor)
    conn.close()


def fetch_books_and_reviews():
    conn = get_db_connection()
    books = conn.execute(SELECT_ALL_BOOKS).fetchall()
    reviews = conn.execute(SELECT_ALL_REVIEWS).fetchall()
    conn.close()
    return books, reviews


def find_user(username, password_hash):
    conn = get_db_connection()
    user = conn.execute(SELECT_USER_BY_CREDENTIALS, (username, password_hash)).fetchone()
    conn.close()
    return user


def save_review(book_id, user_id, review):
    conn = get_db_connection()
    conn.execute(INSERT_REVIEW, (book_id, user_id, review))
    conn.commit()
    conn.close()


def find_books(search_term):
    pattern = f'%{search_term}%'
    conn = get_db_connection()
    results = conn.execute(SEARCH_BOOKS, (pattern, pattern)).fetchall()
    conn.close()
    return results


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    books, reviews = fetch_books_and_reviews()
    return render_template('index.html', books=books, reviews=reviews)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        user = find_user(username, password)
        if user:
            session[SESSION_USER_KEY] = user['id']
            return redirect(url_for('index'))
        return (INVALID_CREDENTIALS_MESSAGE, HTTP_UNAUTHORIZED)
    return render_template('login.html')


@app.route('/add_review', methods=['POST'])
def add_review():
    if SESSION_USER_KEY not in session:
        return redirect(url_for('login'))
    book_id = request.form['book_id']
    review = request.form['review']
    user_id = session[SESSION_USER_KEY]
    save_review(book_id, user_id, review)
    return redirect(url_for('index'))


@app.route('/search')
def search_books():
    search_term = request.args.get('q', '')
    results = find_books(search_term)
    return render_template('search_results.html', results=results, query=search_term)


if __name__ == '__main__':
    init_db()
    app.run(debug=DEBUG_MODE)
