from contextlib import closing

from flask import Flask, request, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)

DB_PATH = 'books.db'
USERNAME_PATTERN = '^[a-zA-Z0-9_]{4,20}$'
SEARCH_SANITIZE_PATTERN = '[;\\\'"\\\\]'
REQUIRED_BOOK_FIELDS = ['title', 'author', 'genre', 'price']

CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users '
    '(id INTEGER PRIMARY KEY, '
    'username TEXT UNIQUE, '
    'password TEXT)'
)
CREATE_BOOKS_TABLE = (
    'CREATE TABLE IF NOT EXISTS books '
    '(id INTEGER PRIMARY KEY, '
    'title TEXT, '
    'author TEXT, '
    'genre TEXT, '
    'price REAL)'
)


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute(CREATE_USERS_TABLE)
        c.execute(CREATE_BOOKS_TABLE)
        conn.commit()


def get_db_connection():
    return sqlite3.connect(DB_PATH)


def _error(message, status):
    return jsonify({'error': message}), status


def _message(message, status):
    return jsonify({'message': message}), status


def _book_to_dict(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


def validate_username(username):
    if not re.match(USERNAME_PATTERN, username):
        raise ValueError('Username must be 4-20 alphanumeric characters')
    return username


def validate_password(password):
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    return password


def validate_book_data(data):
    if not all(field in data for field in REQUIRED_BOOK_FIELDS):
        raise ValueError('Missing required fields')
    try:
        price = float(data['price'])
    except ValueError:
        raise ValueError('Invalid price format')
    if price <= 0:
        raise ValueError('Price must be positive')
    return data


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = validate_username(data.get('username'))
        password = generate_password_hash(validate_password(data.get('password')))
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            try:
                c.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, password),
                )
                conn.commit()
                return _message('User created', 201)
            except sqlite3.IntegrityError:
                return _error('Username already exists', 400)
    except ValueError as e:
        return _error(str(e), 400)
    except Exception:
        return _error('Registration failed', 500)


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return _error('Username and password required', 400)
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute('SELECT password FROM users WHERE username = ?', (username,))
            user = c.fetchone()
        if user and check_password_hash(user[0], password):
            return _message('Login successful', 200)
        return _error('Invalid credentials', 401)
    except Exception:
        return _error('Login failed', 500)


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return _error('Query parameter required', 400)
    search_term = re.sub(SEARCH_SANITIZE_PATTERN, '', search_term)
    pattern = f'%{search_term}%'
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(
            'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?',
            (pattern, pattern),
        )
        books = [_book_to_dict(row) for row in c.fetchall()]
    return jsonify(books)


@app.route('/books/add', methods=['POST'])
def add_book():
    try:
        data = validate_book_data(request.get_json())
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)',
                (data['title'], data['author'], data['genre'], float(data['price'])),
            )
            conn.commit()
        return _message('Book added', 201)
    except ValueError as e:
        return _error(str(e), 400)
    except Exception:
        return _error('Failed to add book', 500)


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM books WHERE id = ?', (book_id,))
            affected = c.rowcount
            conn.commit()
        if affected == 0:
            return _error('Book not found', 404)
        return _message('Book deleted', 200)
    except Exception:
        return _error('Failed to delete book', 500)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
