"""Flask REST API for user registration/login and a simple book catalogue."""

import re
import sqlite3
from contextlib import closing

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DATABASE = 'books.db'

_USERNAME_RE = re.compile('^[a-zA-Z0-9_]{4,20}$')
_SEARCH_TERM_SANITIZER_RE = re.compile(r'[;\'"\\]')

_BOOK_FIELDS = ('title', 'author', 'genre', 'price')


def init_db():
    """Create the users and books tables if they do not already exist."""
    with closing(get_db_connection()) as conn:
        conn.execute(
            'CREATE TABLE IF NOT EXISTS users ('
            'id INTEGER PRIMARY KEY, '
            'username TEXT UNIQUE, '
            'password TEXT)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS books ('
            'id INTEGER PRIMARY KEY, '
            'title TEXT, '
            'author TEXT, '
            'genre TEXT, '
            'price REAL)'
        )
        conn.commit()


def get_db_connection():
    """Return a new connection to the application's SQLite database."""
    return sqlite3.connect(DATABASE)


def validate_username(username):
    if not _USERNAME_RE.match(username):
        raise ValueError('Username must be 4-20 alphanumeric characters')
    return username


def validate_password(password):
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    return password


def validate_book_data(data):
    if not all(field in data for field in _BOOK_FIELDS):
        raise ValueError('Missing required fields')
    try:
        price = float(data['price'])
    except ValueError:
        raise ValueError('Invalid price format')
    if price <= 0:
        raise ValueError('Price must be positive')
    return data


def _book_row_to_dict(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = validate_username(data.get('username'))
        password = generate_password_hash(validate_password(data.get('password')))
        try:
            with closing(get_db_connection()) as conn:
                conn.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, password),
                )
                conn.commit()
            return jsonify({'message': 'User created'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Username already exists'}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Registration failed'}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        with closing(get_db_connection()) as conn:
            user = conn.execute(
                'SELECT password FROM users WHERE username = ?', (username,)
            ).fetchone()
        if user and check_password_hash(user[0], password):
            return jsonify({'message': 'Login successful'}), 200
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception:
        return jsonify({'error': 'Login failed'}), 500


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return jsonify({'error': 'Query parameter required'}), 400
    search_term = _SEARCH_TERM_SANITIZER_RE.sub('', search_term)
    with closing(get_db_connection()) as conn:
        rows = conn.execute(
            'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?',
            (f'%{search_term}%', f'%{search_term}%'),
        ).fetchall()
    return jsonify([_book_row_to_dict(row) for row in rows])


@app.route('/books/add', methods=['POST'])
def add_book():
    try:
        data = validate_book_data(request.get_json())
        with closing(get_db_connection()) as conn:
            conn.execute(
                'INSERT INTO books (title, author, genre, price) '
                'VALUES (?, ?, ?, ?)',
                (
                    data['title'],
                    data['author'],
                    data['genre'],
                    float(data['price']),
                ),
            )
            conn.commit()
        return jsonify({'message': 'Book added'}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Failed to add book'}), 500


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
            affected = cursor.rowcount
            conn.commit()
        if affected == 0:
            return jsonify({'error': 'Book not found'}), 404
        return jsonify({'message': 'Book deleted'}), 200
    except Exception:
        return jsonify({'error': 'Failed to delete book'}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
