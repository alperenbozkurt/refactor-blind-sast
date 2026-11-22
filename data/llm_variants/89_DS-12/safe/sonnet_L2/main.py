from flask import Flask, request, render_template, redirect, url_for, session
import sqlite3
from contextlib import closing
from werkzeug.security import generate_password_hash, check_password_hash
import re

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

DATABASE_PATH = 'books.db'
SECRET_KEY = 'supersecretkey'

USERNAME_PATTERN = '^[a-zA-Z0-9_]{3,20}$'
MIN_PASSWORD_LENGTH = 8
MAX_REVIEW_LENGTH = 1000
SEARCH_TERM_STRIP_PATTERN = '[<>"\\\']'

DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'
DEFAULT_BOOK_TITLE = 'The Great Gatsby'
DEFAULT_BOOK_AUTHOR = 'F. Scott Fitzgerald'

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                  username TEXT UNIQUE, \n'
    '                  password TEXT)'
)
CREATE_BOOKS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS books\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                  title TEXT, \n'
    '                  author TEXT)'
)
CREATE_REVIEWS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS reviews\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                  book_id INTEGER, \n'
    '                  user_id INTEGER, \n'
    '                  review TEXT,\n'
    '                  FOREIGN KEY(book_id) REFERENCES books(id),\n'
    '                  FOREIGN KEY(user_id) REFERENCES users(id))'
)
SCHEMA_STATEMENTS = (
    CREATE_USERS_TABLE_SQL,
    CREATE_BOOKS_TABLE_SQL,
    CREATE_REVIEWS_TABLE_SQL,
)

COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_USER_SQL = 'INSERT INTO users (username, password) VALUES (?, ?)'
INSERT_BOOK_SQL = 'INSERT INTO books (title, author) VALUES (?, ?)'
SELECT_ALL_BOOKS_SQL = 'SELECT * FROM books'
SELECT_ALL_REVIEWS_SQL = (
    '\n'
    '        SELECT reviews.id, books.title, users.username, reviews.review \n'
    '        FROM reviews \n'
    '        JOIN books ON reviews.book_id = books.id\n'
    '        JOIN users ON reviews.user_id = users.id\n'
    '    '
)
SELECT_USER_BY_USERNAME_SQL = 'SELECT * FROM users WHERE username = ?'
SELECT_BOOK_EXISTS_SQL = 'SELECT 1 FROM books WHERE id = ?'
INSERT_REVIEW_SQL = 'INSERT INTO reviews (book_id, user_id, review) VALUES (?, ?, ?)'
SEARCH_BOOKS_SQL = (
    '\n'
    '        SELECT * FROM books \n'
    '        WHERE title LIKE ? OR author LIKE ?\n'
    '    '
)

app = Flask(__name__)
app.secret_key = SECRET_KEY


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #

def _create_schema(cursor):
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)


def _seed_defaults_if_empty(conn, cursor):
    cursor.execute(COUNT_USERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            INSERT_USER_SQL,
            (DEFAULT_ADMIN_USERNAME, generate_password_hash(DEFAULT_ADMIN_PASSWORD)),
        )
        cursor.execute(INSERT_BOOK_SQL, (DEFAULT_BOOK_TITLE, DEFAULT_BOOK_AUTHOR))
        conn.commit()


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    _create_schema(c)
    _seed_defaults_if_empty(conn, c)
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _find_user_by_username(username):
    with closing(get_db_connection()) as conn:
        return conn.execute(SELECT_USER_BY_USERNAME_SQL, (username,)).fetchone()


def _book_exists(conn, book_id):
    return conn.execute(SELECT_BOOK_EXISTS_SQL, (book_id,)).fetchone() is not None


def _insert_review(conn, book_id, user_id, review):
    conn.execute(INSERT_REVIEW_SQL, (book_id, user_id, review))
    conn.commit()


def _search_books(term):
    pattern = f'%{term}%'
    with closing(get_db_connection()) as conn:
        return conn.execute(SEARCH_BOOKS_SQL, (pattern, pattern)).fetchall()


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #

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
    return re.sub(SEARCH_TERM_STRIP_PATTERN, '', term)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route('/')
def index():
    conn = get_db_connection()
    books = conn.execute(SELECT_ALL_BOOKS_SQL).fetchall()
    reviews = conn.execute(SELECT_ALL_REVIEWS_SQL).fetchall()
    conn.close()
    return render_template('index.html', books=books, reviews=reviews)


def _login_error(message, status):
    return (render_template('login.html', error=message), status)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = validate_username(request.form['username'])
            password = request.form['password']
            user = _find_user_by_username(username)
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                return redirect(url_for('index'))
            else:
                return _login_error('Invalid credentials', HTTP_UNAUTHORIZED)
        except ValueError as e:
            return _login_error(str(e), HTTP_BAD_REQUEST)
        except Exception:
            return _login_error('Login failed', HTTP_SERVER_ERROR)
    return render_template('login.html')


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
            return ('Review too long', HTTP_BAD_REQUEST)
        conn = get_db_connection()
        if not _book_exists(conn, book_id):
            conn.close()
            return ('Book not found', HTTP_NOT_FOUND)
        _insert_review(conn, book_id, user_id, review)
        conn.close()
        return redirect(url_for('index'))
    except ValueError:
        return ('Invalid book ID', HTTP_BAD_REQUEST)
    except Exception:
        if conn is not None:
            conn.close()
        return ('Failed to add review', HTTP_SERVER_ERROR)


@app.route('/search')
def search_books():
    search_term = sanitize_search_term(request.args.get('q', ''))
    results = _search_books(search_term)
    return render_template('search_results.html', results=results, query=search_term)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
