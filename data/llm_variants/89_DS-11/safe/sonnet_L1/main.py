from contextlib import closing
import re
import sqlite3

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = 'books.db'

CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                  username TEXT UNIQUE, \n'
    '                  password TEXT)'
)
CREATE_BOOKS_TABLE = (
    'CREATE TABLE IF NOT EXISTS books\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                  title TEXT, \n'
    '                  author TEXT, \n'
    '                  genre TEXT, \n'
    '                  price REAL)'
)

USERNAME_PATTERN = '^[a-zA-Z0-9_]{4,20}$'
SEARCH_FORBIDDEN_CHARS_PATTERN = '[;\\\'"\\\\]'
REQUIRED_BOOK_FIELDS = ['title', 'author', 'genre', 'price']


def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(CREATE_USERS_TABLE)
    c.execute(CREATE_BOOKS_TABLE)
    conn.commit()
    conn.close()


def get_db_connection():
    return sqlite3.connect(DATABASE)


def error_response(message, status):
    return (jsonify({'error': message}), status)


def message_response(message, status):
    return (jsonify({'message': message}), status)


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


def book_row_to_dict(row):
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
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            try:
                c.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, password),
                )
                conn.commit()
                return message_response('User created', 201)
            except sqlite3.IntegrityError:
                return error_response('Username already exists', 400)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception:
        return error_response('Registration failed', 500)


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return error_response('Username and password required', 400)
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute('SELECT password FROM users WHERE username = ?', (username,))
            user = c.fetchone()
        if user and check_password_hash(user[0], password):
            return message_response('Login successful', 200)
        return error_response('Invalid credentials', 401)
    except Exception:
        return error_response('Login failed', 500)


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return error_response('Query parameter required', 400)
    search_term = re.sub(SEARCH_FORBIDDEN_CHARS_PATTERN, '', search_term)
    pattern = f'%{search_term}%'
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(
            'SELECT * FROM books WHERE title LIKE ? OR author LIKE ?',
            (pattern, pattern),
        )
        books = [book_row_to_dict(row) for row in c.fetchall()]
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
        return message_response('Book added', 201)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception:
        return error_response('Failed to add book', 500)


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM books WHERE id = ?', (book_id,))
            affected = c.rowcount
            conn.commit()
        if affected == 0:
            return error_response('Book not found', 404)
        return message_response('Book deleted', 200)
    except Exception:
        return error_response('Failed to delete book', 500)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
