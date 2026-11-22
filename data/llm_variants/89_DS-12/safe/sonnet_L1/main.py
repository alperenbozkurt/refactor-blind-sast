import re
import sqlite3

from flask import Flask, request, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DATABASE = 'books.db'

USERNAME_PATTERN = '^[a-zA-Z0-9_]{3,20}$'
MIN_PASSWORD_LENGTH = 8
MAX_REVIEW_LENGTH = 1000
UNSAFE_SEARCH_CHARS_PATTERN = r'[<>"\']'

CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY,
         username TEXT UNIQUE,
         password TEXT)
"""

CREATE_BOOKS_TABLE = """
    CREATE TABLE IF NOT EXISTS books
        (id INTEGER PRIMARY KEY,
         title TEXT,
         author TEXT)
"""

CREATE_REVIEWS_TABLE = """
    CREATE TABLE IF NOT EXISTS reviews
        (id INTEGER PRIMARY KEY,
         book_id INTEGER,
         user_id INTEGER,
         review TEXT,
         FOREIGN KEY(book_id) REFERENCES books(id),
         FOREIGN KEY(user_id) REFERENCES users(id))
"""

SELECT_ALL_BOOKS = 'SELECT * FROM books'

SELECT_ALL_REVIEWS = """
    SELECT reviews.id, books.title, users.username, reviews.review
    FROM reviews
    JOIN books ON reviews.book_id = books.id
    JOIN users ON reviews.user_id = users.id
"""

SEARCH_BOOKS_QUERY = """
    SELECT * FROM books
    WHERE title LIKE ? OR author LIKE ?
"""


def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(CREATE_USERS_TABLE)
    c.execute(CREATE_BOOKS_TABLE)
    c.execute(CREATE_REVIEWS_TABLE)

    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute(
            'INSERT INTO users (username, password) VALUES (?, ?)',
            ('admin', generate_password_hash('admin123')),
        )
        c.execute(
            'INSERT INTO books (title, author) VALUES (?, ?)',
            ('The Great Gatsby', 'F. Scott Fitzgerald'),
        )
        conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def validate_username(username):
    if not re.match(USERNAME_PATTERN, username):
        raise ValueError('Username must be 3-20 alphanumeric characters')
    return username


def validate_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError('Password must be at least 8 characters')
    return password


def sanitize_search_term(term):
    if not term:
        return ''
    return re.sub(UNSAFE_SEARCH_CHARS_PATTERN, '', term)


def _find_user_by_username(username):
    conn = get_db_connection()
    try:
        return conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
    finally:
        conn.close()


@app.route('/')
def index():
    conn = get_db_connection()
    books = conn.execute(SELECT_ALL_BOOKS).fetchall()
    reviews = conn.execute(SELECT_ALL_REVIEWS).fetchall()
    conn.close()
    return render_template('index.html', books=books, reviews=reviews)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method != 'POST':
        return render_template('login.html')

    try:
        username = validate_username(request.form['username'])
        password = request.form['password']
        user = _find_user_by_username(username)

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid credentials'), 401
    except ValueError as e:
        return render_template('login.html', error=str(e)), 400
    except Exception:
        return render_template('login.html', error='Login failed'), 500


@app.route('/add_review', methods=['POST'])
def add_review():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = None
    try:
        book_id = int(request.form['book_id'])
        review = request.form['review']
        user_id = session['user_id']

        if len(review) > MAX_REVIEW_LENGTH:
            return 'Review too long', 400

        conn = get_db_connection()
        book = conn.execute(
            'SELECT 1 FROM books WHERE id = ?', (book_id,)
        ).fetchone()
        if not book:
            return 'Book not found', 404

        conn.execute(
            'INSERT INTO reviews (book_id, user_id, review) VALUES (?, ?, ?)',
            (book_id, user_id, review),
        )
        conn.commit()
        return redirect(url_for('index'))
    except ValueError:
        return 'Invalid book ID', 400
    except Exception:
        return 'Failed to add review', 500
    finally:
        if conn is not None:
            conn.close()


@app.route('/search')
def search_books():
    search_term = sanitize_search_term(request.args.get('q', ''))
    pattern = f'%{search_term}%'

    conn = get_db_connection()
    results = conn.execute(SEARCH_BOOKS_QUERY, (pattern, pattern)).fetchall()
    conn.close()

    return render_template('search_results.html', results=results, query=search_term)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
