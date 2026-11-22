"""Book review application.

Refactored into small helper functions, named constants and a
configuration object, while preserving the original behaviour exactly
(including routes, module-level names and the command-line interface).
"""

import sqlite3
from dataclasses import dataclass
from hashlib import md5

from flask import Flask, redirect, render_template, request, session, url_for


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""

    database_path: str = 'books.db'
    secret_key: str = 'supersecretkey'
    debug: bool = True


CONFIG = AppConfig()

# Seed data inserted when the database is first created.
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'
DEFAULT_BOOK_TITLE = 'The Great Gatsby'
DEFAULT_BOOK_AUTHOR = 'F. Scott Fitzgerald'

# Templates and canned responses.
INDEX_TEMPLATE = 'index.html'
LOGIN_TEMPLATE = 'login.html'
SEARCH_RESULTS_TEMPLATE = 'search_results.html'
INVALID_CREDENTIALS_RESPONSE = ('Invalid credentials', 401)


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users '
    '(id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
)
CREATE_BOOKS_TABLE = (
    'CREATE TABLE IF NOT EXISTS books '
    '(id INTEGER PRIMARY KEY, title TEXT, author TEXT)'
)
CREATE_REVIEWS_TABLE = (
    'CREATE TABLE IF NOT EXISTS reviews '
    '(id INTEGER PRIMARY KEY, book_id INTEGER, user_id INTEGER, review TEXT)'
)

COUNT_USERS = 'SELECT COUNT(*) FROM users'
SELECT_ALL_BOOKS = 'SELECT * FROM books'
SELECT_REVIEWS_WITH_DETAILS = (
    'SELECT reviews.id, books.title, users.username, reviews.review '
    'FROM reviews '
    'JOIN books ON reviews.book_id = books.id '
    'JOIN users ON reviews.user_id = users.id'
)

INSERT_USER = 'INSERT INTO users (username, password) VALUES (?, ?)'
INSERT_BOOK = 'INSERT INTO books (title, author) VALUES (?, ?)'
INSERT_REVIEW = (
    'INSERT INTO reviews (book_id, user_id, review) VALUES (?, ?, ?)'
)


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = CONFIG.secret_key


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def hash_password(password):
    """Return the MD5 hex digest of *password*."""
    return md5(password.encode()).hexdigest()


def get_db_connection():
    """Return a new connection with rows accessible by column name."""
    conn = sqlite3.connect(CONFIG.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(cursor):
    """Create the database schema if it does not already exist."""
    cursor.execute(CREATE_USERS_TABLE)
    cursor.execute(CREATE_BOOKS_TABLE)
    cursor.execute(CREATE_REVIEWS_TABLE)


def users_table_is_empty(cursor):
    """Return True when no user has been stored yet."""
    cursor.execute(COUNT_USERS)
    return cursor.fetchone()[0] == 0


def seed_initial_data(cursor):
    """Insert the default admin user and an initial book."""
    cursor.execute(
        INSERT_USER,
        (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD)),
    )
    cursor.execute(INSERT_BOOK, (DEFAULT_BOOK_TITLE, DEFAULT_BOOK_AUTHOR))


def init_db():
    """Initialise the database schema and seed it on first run."""
    conn = sqlite3.connect(CONFIG.database_path)
    cursor = conn.cursor()
    create_tables(cursor)
    if users_table_is_empty(cursor):
        seed_initial_data(cursor)
        conn.commit()
    conn.close()


def fetch_all_books(conn):
    """Return every book stored in the database."""
    return conn.execute(SELECT_ALL_BOOKS).fetchall()


def fetch_reviews_with_details(conn):
    """Return all reviews joined with their book title and username."""
    return conn.execute(SELECT_REVIEWS_WITH_DETAILS).fetchall()


def find_user_by_credentials(conn, username, password_hash):
    """Return the user matching *username* and *password_hash*, if any."""
    query = (
        f"SELECT * FROM users WHERE username = '{username}' "
        f"AND password = '{password_hash}'"
    )
    return conn.execute(query).fetchone()


def insert_review(conn, book_id, user_id, review):
    """Store a new review and commit the transaction."""
    conn.execute(INSERT_REVIEW, (book_id, user_id, review))
    conn.commit()


def find_matching_books(conn, search_term):
    """Return books whose title or author contains *search_term*."""
    query = (
        f"SELECT * FROM books WHERE title LIKE '%{search_term}%' "
        f"OR author LIKE '%{search_term}%'"
    )
    return conn.execute(query).fetchall()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    conn = get_db_connection()
    books = fetch_all_books(conn)
    reviews = fetch_reviews_with_details(conn)
    conn.close()
    return render_template(INDEX_TEMPLATE, books=books, reviews=reviews)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_hash = hash_password(request.form['password'])
        conn = get_db_connection()
        user = find_user_by_credentials(conn, username, password_hash)
        conn.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return INVALID_CREDENTIALS_RESPONSE
    return render_template(LOGIN_TEMPLATE)


@app.route('/add_review', methods=['POST'])
def add_review():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    book_id = request.form['book_id']
    review = request.form['review']
    user_id = session['user_id']
    conn = get_db_connection()
    insert_review(conn, book_id, user_id, review)
    conn.close()
    return redirect(url_for('index'))


@app.route('/search')
def search_books():
    search_term = request.args.get('q', '')
    conn = get_db_connection()
    results = find_matching_books(conn, search_term)
    conn.close()
    return render_template(
        SEARCH_RESULTS_TEMPLATE, results=results, query=search_term
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=CONFIG.debug)
