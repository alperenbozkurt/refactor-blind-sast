import sqlite3
from hashlib import md5

from flask import Flask, redirect, render_template, request, session, url_for

DATABASE = 'books.db'

app = Flask(__name__)
app.secret_key = 'supersecretkey'


def hash_password(password):
    return md5(password.encode()).hexdigest()


def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        'CREATE TABLE IF NOT EXISTS users '
        '(id INTEGER PRIMARY KEY, username TEXT, password TEXT)'
    )
    c.execute(
        'CREATE TABLE IF NOT EXISTS books '
        '(id INTEGER PRIMARY KEY, title TEXT, author TEXT)'
    )
    c.execute(
        'CREATE TABLE IF NOT EXISTS reviews '
        '(id INTEGER PRIMARY KEY, book_id INTEGER, user_id INTEGER, review TEXT)'
    )
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute(
            'INSERT INTO users (username, password) VALUES (?, ?)',
            ('admin', hash_password('admin123')),
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


@app.route('/')
def index():
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
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
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
        return 'Invalid credentials', 401
    return render_template('login.html')


@app.route('/add_review', methods=['POST'])
def add_review():
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
