import sqlite3

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DATABASE = 'books.db'

CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY, username TEXT, password TEXT)
"""

CREATE_BOOKS_TABLE = """
    CREATE TABLE IF NOT EXISTS books
        (id INTEGER PRIMARY KEY, title TEXT, author TEXT,
         genre TEXT, price REAL)
"""

REQUIRED_BOOK_FIELDS = ('title', 'author', 'genre', 'price')


def init_db():
    """Create the database tables if they do not already exist."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE)
    cursor.execute(CREATE_BOOKS_TABLE)
    conn.commit()
    conn.close()


def get_db_connection():
    """Return a new connection to the books database."""
    return sqlite3.connect(DATABASE)


def _book_from_row(row):
    """Convert a row from the books table into a JSON-serializable dict."""
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

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (username, password) VALUES (?, ?)',
        (username, password),
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'User created'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT password FROM users WHERE username = '{username}'")
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[0], password):
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'message': 'Invalid credentials'}), 401


@app.route('/books/search', methods=['GET'])
def search_books():
    search_term = request.args.get('query')
    if not search_term:
        return jsonify({'error': 'Query parameter required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    query = f"SELECT * FROM books WHERE title LIKE '%{search_term}%' OR author LIKE '%{search_term}%'"
    cursor.execute(query)
    books = [_book_from_row(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(books)


@app.route('/books/add', methods=['POST'])
def add_book():
    data = request.get_json()
    if not all(field in data for field in REQUIRED_BOOK_FIELDS):
        return jsonify({'error': 'Missing fields'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)',
        (data['title'], data['author'], data['genre'], data['price']),
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'Book added'}), 201


@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Book deleted'}), 200


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
