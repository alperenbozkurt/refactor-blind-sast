import sqlite3

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = 'books.db'

app = Flask(__name__)


def get_db_connection():
    return sqlite3.connect(DATABASE)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS users '
        '(id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
    )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS books '
        '(id INTEGER PRIMARY KEY, title TEXT, author TEXT, '
        'genre TEXT, price REAL)'
    )
    conn.commit()
    conn.close()


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
    query = (
        f"SELECT * FROM books WHERE title LIKE '%{search_term}%' "
        f"OR author LIKE '%{search_term}%'"
    )
    cursor.execute(query)
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
    data = request.get_json()
    required_fields = ['title', 'author', 'genre', 'price']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing fields'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO books (title, author, genre, price) '
        'VALUES (?, ?, ?, ?)',
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
