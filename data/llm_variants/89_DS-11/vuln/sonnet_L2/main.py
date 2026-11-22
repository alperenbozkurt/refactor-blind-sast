from contextlib import closing, contextmanager

from flask import Flask, request, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Configuration / constants
# ---------------------------------------------------------------------------
class Config:
    DATABASE = 'books.db'
    DEBUG = True


REQUIRED_BOOK_FIELDS = ['title', 'author', 'genre', 'price']

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
SELECT_PASSWORD_SQL = 'SELECT password FROM users WHERE username = ?'
SEARCH_BOOKS_SQL = 'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?'
INSERT_BOOK_SQL = 'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)'
DELETE_BOOK_SQL = 'DELETE FROM books WHERE id = ?'

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def init_db():
    with _cursor(commit=True) as c:
        c.execute(CREATE_USERS_TABLE_SQL)
        c.execute(CREATE_BOOKS_TABLE_SQL)


def get_db_connection():
    return sqlite3.connect(Config.DATABASE)


@contextmanager
def _cursor(commit=False):
    """Yield a cursor and always close the connection afterwards."""
    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()


def _row_to_book(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


def _create_user(username, password_hash):
    with _cursor(commit=True) as c:
        c.execute(INSERT_USER_SQL, (username, password_hash))


def _get_password_hash(username):
    with _cursor() as c:
        # Parameterised query (avoids SQL injection).
        c.execute(SELECT_PASSWORD_SQL, (username,))
        return c.fetchone()


def _search_books(search_term):
    pattern = f'%{search_term}%'
    with _cursor() as c:
        c.execute(SEARCH_BOOKS_SQL, (pattern, pattern))
        return [_row_to_book(row) for row in c.fetchall()]


def _insert_book(data):
    values = (data['title'], data['author'], data['genre'], data['price'])
    with _cursor(commit=True) as c:
        c.execute(INSERT_BOOK_SQL, values)


def _delete_book(book_id):
    with _cursor(commit=True) as c:
        c.execute(DELETE_BOOK_SQL, (book_id,))


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def _message(text, status):
    return (jsonify({'message': text}), status)


def _error(text, status):
    return (jsonify({'error': text}), status)


def _has_required_fields(data):
    return all((field in data for field in REQUIRED_BOOK_FIELDS))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = generate_password_hash(data.get('password'))
    _create_user(username, password)
    return _message('User created', HTTP_CREATED)


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = _get_password_hash(username)
    if user and check_password_hash(user[0], password):
        return _message('Login successful', HTTP_OK)
    return _message('Invalid credentials', HTTP_UNAUTHORIZED)


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return _error('Query parameter required', HTTP_BAD_REQUEST)
    return jsonify(_search_books(search_term))


@app.route('/books/add', methods=['POST'])
def add_book():
    data = request.get_json()
    if not _has_required_fields(data):
        return _error('Missing fields', HTTP_BAD_REQUEST)
    _insert_book(data)
    return _message('Book added', HTTP_CREATED)


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    _delete_book(book_id)
    return _message('Book deleted', HTTP_OK)


if __name__ == '__main__':
    init_db()
    app.run(debug=Config.DEBUG)
