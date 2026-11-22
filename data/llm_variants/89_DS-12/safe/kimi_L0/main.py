import re
import sqlite3
from contextlib import closing

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DATABASE = 'books.db'

USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
UNSAFE_SEARCH_CHARS_PATTERN = re.compile('[<>"\']')

SCHEMA_STATEMENTS = (
    '''
    CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY,
         username TEXT UNIQUE,
         password TEXT)
    ''',
    '''
    CREATE TABLE IF NOT EXISTS books
        (id INTEGER PRIMARY KEY,
         title TEXT,
         author TEXT)
    ''',
    '''
    CREATE TABLE IF NOT EXISTS reviews
        (id INTEGER PRIMARY KEY,
         book_id INTEGER,
         user_id INTEGER,
         review TEXT,
         FOREIGN KEY(book_id) REFERENCES books(id),
         FOREIGN KEY(user_id) REFERENCES users(id))
    ''',
)

REVIEWS_WITH_DETAILS_QUERY = '''
    SELECT reviews.id, books.title, users.username, reviews.review
    FROM reviews
    JOIN books ON reviews.book_id = books.id
    JOIN users ON reviews.user_id = users.id
'''

SEARCH_BOOKS_QUERY = '''
    SELECT * FROM books
    WHERE title LIKE ? OR author LIKE ?
'''


def init_db():
    with closing(sqlite3.connect(DATABASE)) as conn:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
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


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def validate_username(username):
    if not USERNAME_PATTERN.match(username):
        raise ValueError('Username must be 3-20 alphanumeric characters')
    return username


def validate_password(password):
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    return password


def sanitize_search_term(term):
    if not term:
        return ''
    return UNSAFE_SEARCH_CHARS_PATTERN.sub('', term)


@app.route('/')
def index():
    with closing(get_db_connection()) as conn:
        books = conn.execute('SELECT * FROM books').fetchall()
        reviews = conn.execute(REVIEWS_WITH_DETAILS_QUERY).fetchall()
    return render_template('index.html', books=books, reviews=reviews)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = validate_username(request.form['username'])
            password = request.form['password']
            with closing(get_db_connection()) as conn:
                user = conn.execute(
                    'SELECT * FROM users WHERE username = ?', (username,)
                ).fetchone()
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        book_id = int(request.form['book_id'])
        review = request.form['review']
        user_id = session['user_id']
        if len(review) > 1000:
            return 'Review too long', 400
        with closing(get_db_connection()) as conn:
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


@app.route('/search')
def search_books():
    search_term = sanitize_search_term(request.args.get('q', ''))
    with closing(get_db_connection()) as conn:
        results = conn.execute(
            SEARCH_BOOKS_QUERY, (f'%{search_term}%', f'%{search_term}%')
        ).fetchall()
    return render_template('search_results.html', results=results, query=search_term)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
