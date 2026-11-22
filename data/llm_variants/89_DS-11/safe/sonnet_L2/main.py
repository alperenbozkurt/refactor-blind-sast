from contextlib import closing

from flask import Flask, request, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)

# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------
DATABASE_PATH = 'books.db'

USERNAME_PATTERN = '^[a-zA-Z0-9_]{4,20}$'
MIN_PASSWORD_LENGTH = 8
REQUIRED_BOOK_FIELDS = ['title', 'author', 'genre', 'price']
SEARCH_SANITIZE_PATTERN = '[;\\\'"\\\\]'

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

# --------------------------------------------------------------------------
# SQL statements
# --------------------------------------------------------------------------
CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                  username TEXT UNIQUE, \n'
    '                  password TEXT)'
)
CREATE_BOOKS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS books\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                  title TEXT, \n'
    '                  author TEXT, \n'
    '                  genre TEXT, \n'
    '                  price REAL)'
)
INSERT_USER_SQL = 'INSERT INTO users (username, password) VALUES (?, ?)'
SELECT_USER_PASSWORD_SQL = 'SELECT password FROM users WHERE username = ?'
SEARCH_BOOKS_SQL = 'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?'
INSERT_BOOK_SQL = 'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)'
DELETE_BOOK_SQL = 'DELETE FROM books WHERE id = ?'


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute(CREATE_USERS_TABLE_SQL)
    c.execute(CREATE_BOOKS_TABLE_SQL)
    conn.commit()
    conn.close()


def get_db_connection():
    return sqlite3.connect(DATABASE_PATH)


def _row_to_book(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


# --------------------------------------------------------------------------
# Response helpers
# --------------------------------------------------------------------------
def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _message_response(message, status):
    return (jsonify({'message': message}), status)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def validate_username(username):
    if not re.match(USERNAME_PATTERN, username):
        raise ValueError('Username must be 4-20 alphanumeric characters')
    return username


def validate_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError('Password must be at least 8 characters')
    return password


def validate_book_data(data):
    if not all((field in data for field in REQUIRED_BOOK_FIELDS)):
        raise ValueError('Missing required fields')
    try:
        price = float(data['price'])
    except ValueError:
        raise ValueError('Invalid price format')
    if price <= 0:
        raise ValueError('Price must be positive')
    return data


def _sanitize_search_term(term):
    return re.sub(SEARCH_SANITIZE_PATTERN, '', term)


# --------------------------------------------------------------------------
# Data access operations
# --------------------------------------------------------------------------
def _insert_user(username, password_hash):
    """Insert a user; raises sqlite3.IntegrityError on duplicate username."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(INSERT_USER_SQL, (username, password_hash))
        conn.commit()


def _fetch_password_hash(username):
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(SELECT_USER_PASSWORD_SQL, (username,))
        return c.fetchone()


def _find_books(search_term):
    pattern = f'%{search_term}%'
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(SEARCH_BOOKS_SQL, (pattern, pattern))
        return [_row_to_book(row) for row in c.fetchall()]


def _insert_book(data):
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(
            INSERT_BOOK_SQL,
            (data['title'], data['author'], data['genre'], float(data['price'])),
        )
        conn.commit()


def _delete_book_by_id(book_id):
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(DELETE_BOOK_SQL, (book_id,))
        affected = c.rowcount
        conn.commit()
        return affected


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = validate_username(data.get('username'))
        password = generate_password_hash(validate_password(data.get('password')))
        try:
            _insert_user(username, password)
            return _message_response('User created', HTTP_CREATED)
        except sqlite3.IntegrityError:
            return _error_response('Username already exists', HTTP_BAD_REQUEST)
    except ValueError as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)
    except Exception as e:
        return _error_response('Registration failed', HTTP_INTERNAL_ERROR)


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return _error_response('Username and password required', HTTP_BAD_REQUEST)
        user = _fetch_password_hash(username)
        if user and check_password_hash(user[0], password):
            return _message_response('Login successful', HTTP_OK)
        return _error_response('Invalid credentials', HTTP_UNAUTHORIZED)
    except Exception as e:
        return _error_response('Login failed', HTTP_INTERNAL_ERROR)


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return _error_response('Query parameter required', HTTP_BAD_REQUEST)
    search_term = _sanitize_search_term(search_term)
    return jsonify(_find_books(search_term))


@app.route('/books/add', methods=['POST'])
def add_book():
    try:
        data = validate_book_data(request.get_json())
        _insert_book(data)
        return _message_response('Book added', HTTP_CREATED)
    except ValueError as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)
    except Exception as e:
        return _error_response('Failed to add book', HTTP_INTERNAL_ERROR)


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    try:
        affected = _delete_book_by_id(book_id)
        if affected == 0:
            return _error_response('Book not found', HTTP_NOT_FOUND)
        return _message_response('Book deleted', HTTP_OK)
    except Exception as e:
        return _error_response('Failed to delete book', HTTP_INTERNAL_ERROR)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
