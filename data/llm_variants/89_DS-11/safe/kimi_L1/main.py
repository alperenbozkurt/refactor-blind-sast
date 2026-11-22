"""Flask API for user accounts and a book catalogue backed by SQLite."""

import re
import sqlite3

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)


def init_db():
    """Create the users and books tables if they do not already exist."""
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS users ('
        'id INTEGER PRIMARY KEY, '
        'username TEXT UNIQUE, '
        'password TEXT)'
    )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS books ('
        'id INTEGER PRIMARY KEY, '
        'title TEXT, '
        'author TEXT, '
        'genre TEXT, '
        'price REAL)'
    )
    conn.commit()
    conn.close()


def get_db_connection():
    """Return a new connection to the books SQLite database."""
    return sqlite3.connect('books.db')


def validate_username(username):
    """Return the username if it is 4-20 alphanumeric characters.

    Raises:
        ValueError: If the username does not match the required format.
    """
    if not re.match(r'^[a-zA-Z0-9_]{4,20}$', username):
        raise ValueError('Username must be 4-20 alphanumeric characters')
    return username


def validate_password(password):
    """Return the password if it is at least 8 characters long.

    Raises:
        ValueError: If the password is too short.
    """
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    return password


def validate_book_data(data):
    """Return the book data if all required fields are present and valid.

    Raises:
        ValueError: If a required field is missing or the price is invalid.
    """
    required_fields = ['title', 'author', 'genre', 'price']
    if not all(field in data for field in required_fields):
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
    """Create a new user account."""
    try:
        data = request.get_json()
        username = validate_username(data.get('username'))
        password = generate_password_hash(validate_password(data.get('password')))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, password),
            )
            conn.commit()
            return jsonify({'message': 'User created'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Username already exists'}), 400
        finally:
            conn.close()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Registration failed'}), 500


@app.route('/login', methods=['POST'])
def login():
    """Authenticate a user by username and password."""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            return jsonify({'message': 'Login successful'}), 200
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception:
        return jsonify({'error': 'Login failed'}), 500


@app.route('/books/search', methods=['GET'])
def search_books():
    """Search books by title or author using the ``query`` parameter."""
    search_term = request.args.get('query')
    if not search_term:
        return jsonify({'error': 'Query parameter required'}), 400

    # Strip characters that are not allowed in the search term.
    search_term = re.sub(r'[;\'"\\]', '', search_term)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?',
        (f'%{search_term}%', f'%{search_term}%'),
    )
    books = [
        {
            'id': row[0],
            'title': row[1],
            'author': row[2],
            'genre': row[3],
            'price': row[4],
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return jsonify(books)


@app.route('/books/add', methods=['POST'])
def add_book():
    """Add a new book to the catalogue."""
    try:
        data = validate_book_data(request.get_json())
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)',
            (data['title'], data['author'], data['genre'], float(data['price'])),
        )
        conn.commit()
        conn.close()
        return jsonify({'message': 'Book added'}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': 'Failed to add book'}), 500


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Delete the book with the given ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM books WHERE id = ?', (book_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        if affected == 0:
            return jsonify({'error': 'Book not found'}), 404
        return jsonify({'message': 'Book deleted'}), 200
    except Exception:
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': 'Failed to delete book'}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
