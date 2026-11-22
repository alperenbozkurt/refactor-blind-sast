"""Bookstore API service.

A small Flask application exposing user registration/login endpoints and a
book catalogue (search, add, delete), backed by a SQLite database.
"""

import re
import sqlite3
from contextlib import closing

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Application-wide configuration values."""

    DATABASE = 'books.db'
    DEBUG = False


# Validation rules
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{4,20}$')
MIN_PASSWORD_LENGTH = 8
REQUIRED_BOOK_FIELDS = ('title', 'author', 'genre', 'price')
SEARCH_TERM_SANITIZER = re.compile(r'[;\'"\\]')

# Validation error messages
ERR_INVALID_USERNAME = 'Username must be 4-20 alphanumeric characters'
ERR_INVALID_PASSWORD = 'Password must be at least 8 characters'
ERR_MISSING_BOOK_FIELDS = 'Missing required fields'
ERR_INVALID_PRICE = 'Invalid price format'
ERR_NON_POSITIVE_PRICE = 'Price must be positive'

# Response messages
MSG_USER_CREATED = 'User created'
MSG_LOGIN_SUCCESSFUL = 'Login successful'
MSG_BOOK_ADDED = 'Book added'
MSG_BOOK_DELETED = 'Book deleted'
ERR_USERNAME_TAKEN = 'Username already exists'
ERR_REGISTRATION_FAILED = 'Registration failed'
ERR_CREDENTIALS_REQUIRED = 'Username and password required'
ERR_INVALID_CREDENTIALS = 'Invalid credentials'
ERR_LOGIN_FAILED = 'Login failed'
ERR_QUERY_REQUIRED = 'Query parameter required'
ERR_ADD_BOOK_FAILED = 'Failed to add book'
ERR_DELETE_BOOK_FAILED = 'Failed to delete book'
ERR_BOOK_NOT_FOUND = 'Book not found'

# SQL statements
SQL_CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users '
    '(id INTEGER PRIMARY KEY, '
    'username TEXT UNIQUE, '
    'password TEXT)'
)
SQL_CREATE_BOOKS_TABLE = (
    'CREATE TABLE IF NOT EXISTS books '
    '(id INTEGER PRIMARY KEY, '
    'title TEXT, '
    'author TEXT, '
    'genre TEXT, '
    'price REAL)'
)
SQL_INSERT_USER = 'INSERT INTO users (username, password) VALUES (?, ?)'
SQL_SELECT_USER_PASSWORD = 'SELECT password FROM users WHERE username = ?'
SQL_SEARCH_BOOKS = 'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?'
SQL_INSERT_BOOK = (
    'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)'
)
SQL_DELETE_BOOK = 'DELETE FROM books WHERE id = ?'


app = Flask(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection():
    """Open a new connection to the application database."""
    return sqlite3.connect(Config.DATABASE)


def init_db():
    """Create the database tables if they do not already exist."""
    with closing(get_db_connection()) as conn:
        conn.execute(SQL_CREATE_USERS_TABLE)
        conn.execute(SQL_CREATE_BOOKS_TABLE)
        conn.commit()


def _insert_user(username, password_hash):
    """Insert a user row, letting sqlite3.IntegrityError propagate."""
    with closing(get_db_connection()) as conn:
        conn.execute(SQL_INSERT_USER, (username, password_hash))
        conn.commit()


def _select_user_password(username):
    """Return the (password,) row for username, or None if not found."""
    with closing(get_db_connection()) as conn:
        return conn.execute(SQL_SELECT_USER_PASSWORD, (username,)).fetchone()


def _insert_book(data):
    """Insert a book row from validated book data."""
    with closing(get_db_connection()) as conn:
        conn.execute(
            SQL_INSERT_BOOK,
            (data['title'], data['author'], data['genre'], float(data['price'])),
        )
        conn.commit()


def _delete_book(book_id):
    """Delete a book row and return the number of affected rows."""
    with closing(get_db_connection()) as conn:
        cursor = conn.execute(SQL_DELETE_BOOK, (book_id,))
        affected = cursor.rowcount
        conn.commit()
        return affected


def _search_books(search_term):
    """Return book dicts whose title or author contains the search term."""
    like_pattern = f'%{search_term}%'
    with closing(get_db_connection()) as conn:
        rows = conn.execute(SQL_SEARCH_BOOKS, (like_pattern, like_pattern)).fetchall()
    return [_row_to_book(row) for row in rows]


def _row_to_book(row):
    """Convert a books table row into a JSON-serializable dict."""
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_username(username):
    if not USERNAME_PATTERN.match(username):
        raise ValueError(ERR_INVALID_USERNAME)
    return username


def validate_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(ERR_INVALID_PASSWORD)
    return password


def validate_book_data(data):
    if not all((field in data for field in REQUIRED_BOOK_FIELDS)):
        raise ValueError(ERR_MISSING_BOOK_FIELDS)
    try:
        price = float(data['price'])
    except ValueError:
        raise ValueError(ERR_INVALID_PRICE)
    if price <= 0:
        raise ValueError(ERR_NON_POSITIVE_PRICE)
    return data


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _message_response(message, status):
    return (jsonify({'message': message}), status)


def _error_response(message, status):
    return (jsonify({'error': message}), status)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = validate_username(data.get('username'))
        password_hash = generate_password_hash(validate_password(data.get('password')))
        try:
            _insert_user(username, password_hash)
        except sqlite3.IntegrityError:
            return _error_response(ERR_USERNAME_TAKEN, 400)
        return _message_response(MSG_USER_CREATED, 201)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(ERR_REGISTRATION_FAILED, 500)


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return _error_response(ERR_CREDENTIALS_REQUIRED, 400)
        user = _select_user_password(username)
        if user and check_password_hash(user[0], password):
            return _message_response(MSG_LOGIN_SUCCESSFUL, 200)
        return _error_response(ERR_INVALID_CREDENTIALS, 401)
    except Exception:
        return _error_response(ERR_LOGIN_FAILED, 500)


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return _error_response(ERR_QUERY_REQUIRED, 400)
    search_term = SEARCH_TERM_SANITIZER.sub('', search_term)
    return jsonify(_search_books(search_term))


@app.route('/books/add', methods=['POST'])
def add_book():
    try:
        data = validate_book_data(request.get_json())
        _insert_book(data)
        return _message_response(MSG_BOOK_ADDED, 201)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(ERR_ADD_BOOK_FAILED, 500)


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    try:
        affected = _delete_book(book_id)
        if affected == 0:
            return _error_response(ERR_BOOK_NOT_FOUND, 404)
        return _message_response(MSG_BOOK_DELETED, 200)
    except Exception:
        return _error_response(ERR_DELETE_BOOK_FAILED, 500)


if __name__ == '__main__':
    init_db()
    app.run(debug=Config.DEBUG)
