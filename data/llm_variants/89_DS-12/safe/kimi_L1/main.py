"""Flask application for managing books and user reviews."""

import re
import sqlite3

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = 'books.db'

USERNAME_PATTERN = '^[a-zA-Z0-9_]{3,20}$'
UNSAFE_SEARCH_CHARS = '[<>"\\\']'

MIN_PASSWORD_LENGTH = 8
MAX_REVIEW_LENGTH = 1000

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

app = Flask(__name__)
app.secret_key = 'supersecretkey'


def init_db():
    """Create the database tables and seed initial data if empty."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE)
    cursor.execute(CREATE_BOOKS_TABLE)
    cursor.execute(CREATE_REVIEWS_TABLE)
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO users (username, password) VALUES (?, ?)',
            ('admin', generate_password_hash('admin123')),
        )
        cursor.execute(
            'INSERT INTO books (title, author) VALUES (?, ?)',
            ('The Great Gatsby', 'F. Scott Fitzgerald'),
        )
        conn.commit()
    conn.close()


def get_db_connection():
    """Return a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def validate_username(username):
    """Ensure the username is 3-20 alphanumeric characters or underscores."""
    if not re.match(USERNAME_PATTERN, username):
        raise ValueError('Username must be 3-20 alphanumeric characters')
    return username


def validate_password(password):
    """Ensure the password meets the minimum length requirement."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError('Password must be at least 8 characters')
    return password


def sanitize_search_term(term):
    """Strip potentially unsafe characters from a search term."""
    if not term:
        return ''
    return re.sub(UNSAFE_SEARCH_CHARS, '', term)


@app.route('/')
def index():
    """Render the home page with all books and reviews."""
    conn = get_db_connection()
    books = conn.execute(SELECT_ALL_BOOKS).fetchall()
    reviews = conn.execute(SELECT_ALL_REVIEWS).fetchall()
    conn.close()
    return render_template('index.html', books=books, reviews=reviews)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticate a user and start a session."""
    if request.method == 'POST':
        try:
            username = validate_username(request.form['username'])
            password = request.form['password']
            conn = get_db_connection()
            user = conn.execute(
                'SELECT * FROM users WHERE username = ?', (username,)
            ).fetchone()
            conn.close()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                return redirect(url_for('index'))
            return render_template('login.html', error='Invalid credentials'), 401
        except ValueError as e:
            return render_template('login.html', error=str(e)), 400
        except Exception:
            return render_template('login.html', error='Login failed'), 500
    return render_template('login.html')


@app.route('/add_review', methods=['POST'])
def add_review():
    """Add a review for a book on behalf of the logged-in user."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
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
            conn.close()
            return 'Book not found', 404
        conn.execute(
            'INSERT INTO reviews (book_id, user_id, review) VALUES (?, ?, ?)',
            (book_id, user_id, review),
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    except ValueError:
        return 'Invalid book ID', 400
    except Exception:
        if 'conn' in locals():
            conn.close()
        return 'Failed to add review', 500


@app.route('/search')
def search_books():
    """Search books by title or author using a sanitized search term."""
    search_term = sanitize_search_term(request.args.get('q', ''))
    conn = get_db_connection()
    results = conn.execute(
        SEARCH_BOOKS_QUERY, (f'%{search_term}%', f'%{search_term}%')
    ).fetchall()
    conn.close()
    return render_template('search_results.html', results=results, query=search_term)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
