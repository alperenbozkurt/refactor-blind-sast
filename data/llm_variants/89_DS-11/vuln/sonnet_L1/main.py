import sqlite3

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = 'books.db'

CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
)
CREATE_BOOKS_TABLE = (
    'CREATE TABLE IF NOT EXISTS books\n'
    '                 (id INTEGER PRIMARY KEY, title TEXT, author TEXT, \n'
    '                 genre TEXT, price REAL)'
)

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


def row_to_book(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'genre': row[3],
        'price': row[4],
    }


def message_response(message, status):
    return jsonify({'message': message}), status


def error_response(error, status):
    return jsonify({'error': error}), status


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = generate_password_hash(data.get('password'))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        'INSERT INTO users (username, password) VALUES (?, ?)',
        (username, password),
    )
    conn.commit()
    conn.close()

    return message_response('User created', 201)


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    c = conn.cursor()
    # NOTE: query built via string interpolation (SQL injection risk); kept
    # unchanged to preserve existing behaviour.
    c.execute(f"SELECT password FROM users WHERE username = '{username}'")
    user = c.fetchone()
    conn.close()

    if user and check_password_hash(user[0], password):
        return message_response('Login successful', 200)
    return message_response('Invalid credentials', 401)


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return error_response('Query parameter required', 400)

    conn = get_db_connection()
    c = conn.cursor()
    # NOTE: query built via string interpolation (SQL injection risk); kept
    # unchanged to preserve existing behaviour.
    query = (
        f"SELECT * FROM books WHERE title LIKE '%{search_term}%' "
        f"OR author LIKE '%{search_term}%'"
    )
    c.execute(query)
    books = [row_to_book(row) for row in c.fetchall()]
    conn.close()

    return jsonify(books)


@app.route('/books/add', methods=['POST'])
def add_book():
    data = request.get_json()
    if not all(field in data for field in REQUIRED_BOOK_FIELDS):
        return error_response('Missing fields', 400)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)',
        (data['title'], data['author'], data['genre'], data['price']),
    )
    conn.commit()
    conn.close()

    return message_response('Book added', 201)


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()

    return message_response('Book deleted', 200)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
