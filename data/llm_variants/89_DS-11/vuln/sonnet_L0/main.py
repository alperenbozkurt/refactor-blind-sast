from contextlib import closing
import sqlite3

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = 'books.db'
BOOK_REQUIRED_FIELDS = ['title', 'author', 'genre', 'price']


def init_db():
    with closing(sqlite3.connect(DATABASE)) as conn:
        c = conn.cursor()
        c.execute(
            'CREATE TABLE IF NOT EXISTS users '
            '(id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
        )
        c.execute(
            'CREATE TABLE IF NOT EXISTS books '
            '(id INTEGER PRIMARY KEY, title TEXT, author TEXT, '
            'genre TEXT, price REAL)'
        )
        conn.commit()


def get_db_connection():
    return sqlite3.connect(DATABASE)


def _write(query, params=()):
    """Execute a modifying statement and commit it."""
    with closing(get_db_connection()) as conn:
        conn.cursor().execute(query, params)
        conn.commit()


def _fetch(query, params=(), one=False):
    """Execute a SELECT statement and return one row or all rows."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(query, params)
        return c.fetchone() if one else c.fetchall()


def _book_to_dict(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = generate_password_hash(data.get('password'))
    _write(
        'INSERT INTO users (username, password) VALUES (?, ?)',
        (username, password),
    )
    return jsonify({'message': 'User created'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = _fetch(
        'SELECT password FROM users WHERE username = ?',
        (username,),
        one=True,
    )
    if user and check_password_hash(user[0], password):
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'message': 'Invalid credentials'}), 401


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return jsonify({'error': 'Query parameter required'}), 400
    pattern = f'%{search_term}%'
    rows = _fetch(
        'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?',
        (pattern, pattern),
    )
    return jsonify([_book_to_dict(row) for row in rows])


@app.route('/books/add', methods=['POST'])
def add_book():
    data = request.get_json()
    if not all(field in data for field in BOOK_REQUIRED_FIELDS):
        return jsonify({'error': 'Missing fields'}), 400
    _write(
        'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)',
        tuple(data[field] for field in BOOK_REQUIRED_FIELDS),
    )
    return jsonify({'message': 'Book added'}), 201


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    _write('DELETE FROM books WHERE id = ?', (book_id,))
    return jsonify({'message': 'Book deleted'}), 200


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
