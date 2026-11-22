"""Flask bookstore API backed by a SQLite database."""

import sqlite3
from contextlib import contextmanager

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Runtime configuration for the application."""

    DATABASE_PATH = 'books.db'
    DEBUG = True


config = Config()

app = Flask(__name__)


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
)
CREATE_BOOKS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS books\n'
    '                 (id INTEGER PRIMARY KEY, title TEXT, author TEXT, \n'
    '                 genre TEXT, price REAL)'
)

INSERT_USER_SQL = 'INSERT INTO users (username, password) VALUES (?, ?)'
SELECT_PASSWORD_BY_USERNAME_SQL = (
    "SELECT password FROM users WHERE username = '{username}'"
)
SEARCH_BOOKS_SQL = (
    "SELECT * FROM books WHERE title LIKE '%{search_term}%' "
    "OR author LIKE '%{search_term}%'"
)
INSERT_BOOK_SQL = (
    'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)'
)
DELETE_BOOK_SQL = 'DELETE FROM books WHERE id = ?'


# ---------------------------------------------------------------------------
# Other constants
# ---------------------------------------------------------------------------

REQUIRED_BOOK_FIELDS = ['title', 'author', 'genre', 'price']

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401

USER_CREATED_MESSAGE = 'User created'
LOGIN_SUCCESS_MESSAGE = 'Login successful'
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'
BOOK_ADDED_MESSAGE = 'Book added'
BOOK_DELETED_MESSAGE = 'Book deleted'
QUERY_REQUIRED_ERROR = 'Query parameter required'
MISSING_FIELDS_ERROR = 'Missing fields'


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection():
    """Return a new connection to the application database."""
    return sqlite3.connect(config.DATABASE_PATH)


@contextmanager
def _db_cursor(commit=False):
    """Yield a cursor, committing on success if requested and always closing."""
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        yield cursor
        if commit:
            connection.commit()
    finally:
        connection.close()


def init_db():
    """Create the database tables if they do not already exist."""
    with _db_cursor(commit=True) as cursor:
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(CREATE_BOOKS_TABLE_SQL)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _message_response(text, status_code):
    """Build a ``{'message': ...}`` JSON response tuple."""
    return jsonify({'message': text}), status_code


def _error_response(text, status_code):
    """Build an ``{'error': ...}`` JSON response tuple."""
    return jsonify({'error': text}), status_code


def _book_row_to_dict(row):
    """Convert a books table row into its JSON-serialisable dictionary."""
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = generate_password_hash(data.get('password'))
    with _db_cursor(commit=True) as cursor:
        cursor.execute(INSERT_USER_SQL, (username, password))
    return _message_response(USER_CREATED_MESSAGE, HTTP_CREATED)


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    with _db_cursor() as cursor:
        cursor.execute(SELECT_PASSWORD_BY_USERNAME_SQL.format(username=username))
        user = cursor.fetchone()
    if user and check_password_hash(user[0], password):
        return _message_response(LOGIN_SUCCESS_MESSAGE, HTTP_OK)
    return _message_response(INVALID_CREDENTIALS_MESSAGE, HTTP_UNAUTHORIZED)


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return _error_response(QUERY_REQUIRED_ERROR, HTTP_BAD_REQUEST)
    query = SEARCH_BOOKS_SQL.format(search_term=search_term)
    with _db_cursor() as cursor:
        cursor.execute(query)
        books = [_book_row_to_dict(row) for row in cursor.fetchall()]
    return jsonify(books)


@app.route('/books/add', methods=['POST'])
def add_book():
    data = request.get_json()
    if not all(field in data for field in REQUIRED_BOOK_FIELDS):
        return _error_response(MISSING_FIELDS_ERROR, HTTP_BAD_REQUEST)
    book = (data['title'], data['author'], data['genre'], data['price'])
    with _db_cursor(commit=True) as cursor:
        cursor.execute(INSERT_BOOK_SQL, book)
    return _message_response(BOOK_ADDED_MESSAGE, HTTP_CREATED)


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    with _db_cursor(commit=True) as cursor:
        cursor.execute(DELETE_BOOK_SQL, (book_id,))
    return _message_response(BOOK_DELETED_MESSAGE, HTTP_OK)


if __name__ == '__main__':
    init_db()
    app.run(debug=config.DEBUG)
