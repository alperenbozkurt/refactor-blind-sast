"""Simple Flask application for listing and reviewing books."""

from flask import Flask, request, render_template, redirect, url_for, session
import sqlite3
from hashlib import md5

app = Flask(__name__)
app.secret_key = 'supersecretkey'


def init_db():
    """Create the database tables and seed default data if none exists."""
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS users '
        '(id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
    )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS books '
        '(id INTEGER PRIMARY KEY, title TEXT, author TEXT)'
    )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS reviews '
        '(id INTEGER PRIMARY KEY, book_id INTEGER, user_id INTEGER, review TEXT)'
    )
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO users (username, password) VALUES (?, ?)',
            ('admin', md5('admin123'.encode()).hexdigest()),
        )
        cursor.execute(
            'INSERT INTO books (title, author) VALUES (?, ?)',
            ('The Great Gatsby', 'F. Scott Fitzgerald'),
        )
        conn.commit()
    conn.close()


def get_db_connection():
    """Return a new SQLite connection with rows accessible by column name."""
    conn = sqlite3.connect('books.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """Render the home page with all books and reviews."""
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    reviews = conn.execute(
        'SELECT reviews.id, books.title, users.username, reviews.review '
        'FROM reviews '
        'JOIN books ON reviews.book_id = books.id '
        'JOIN users ON reviews.user_id = users.id'
    ).fetchall()
    conn.close()
    return render_template('index.html', books=books, reviews=reviews)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticate a user and store their id in the session."""
    if request.method == 'POST':
        username = request.form['username']
        password = md5(request.form['password'].encode()).hexdigest()
        conn = get_db_connection()
        query = (
            f"SELECT * FROM users WHERE username = '{username}' "
            f"AND password = '{password}'"
        )
        user = conn.execute(query).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return ('Invalid credentials', 401)
    return render_template('login.html')


@app.route('/add_review', methods=['POST'])
def add_review():
    """Add a review for a book on behalf of the logged-in user."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    book_id = request.form['book_id']
    review = request.form['review']
    user_id = session['user_id']
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO reviews (book_id, user_id, review) VALUES (?, ?, ?)',
        (book_id, user_id, review),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/search')
def search_books():
    """Search books by title or author and render the results."""
    search_term = request.args.get('q', '')
    conn = get_db_connection()
    query = (
        f"SELECT * FROM books WHERE title LIKE '%{search_term}%' "
        f"OR author LIKE '%{search_term}%'"
    )
    results = conn.execute(query).fetchall()
    conn.close()
    return render_template('search_results.html', results=results, query=search_term)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
