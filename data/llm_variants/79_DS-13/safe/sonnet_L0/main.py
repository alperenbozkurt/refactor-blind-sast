from contextlib import contextmanager
import hashlib
import secrets
import sqlite3
import uuid
from html import escape

from bottle import Bottle, run, request, response, template, redirect, abort

app = Bottle()
COOKIE_SECRET = secrets.token_urlsafe(32)

DB_PATH = 'user_profiles.db'
PBKDF2_ITERATIONS = 100000

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 username TEXT UNIQUE,\n'
    '                 password TEXT,\n'
    '                 bio TEXT,\n'
    '                 theme TEXT)'
)

INDEX_HTML = (
    '\n'
    '        <h1>Welcome to MyApp</h1>\n'
    '        <a href="/login">Login</a> | \n'
    '        <a href="/register">Register</a>\n'
    '    '
)

REGISTER_HTML = '''
        <h1>Register</h1>
        <form method="POST">
            Username: <input type="text" name="username" required><br>
            Password: <input type="password" name="password" required minlength="8"><br>
            <input type="submit" value="Register">
        </form>
    '''

LOGIN_HTML = '''
        <h1>Login</h1>
        <form method="POST">
            Username: <input type="text" name="username" required><br>
            Password: <input type="password" name="password" required><br>
            <input type="submit" value="Login">
        </form>
    '''

PROFILE_TEMPLATE = '''
        <h1>Profile: {{username}}</h1>
        <div id="user-bio">{{!bio}}</div>
        <form method="POST">
            <textarea name="bio">{{bio}}</textarea><br>
            <input type="submit" value="Update Bio">
        </form>
        <a href="/logout">Logout</a>
    '''


@contextmanager
def _db_cursor():
    """Yield a cursor; commit and close the connection when done."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _db_cursor() as c:
        c.execute(CREATE_USERS_TABLE_SQL)


init_db()


def _derive_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()


def hash_password(password):
    salt = secrets.token_hex(16)
    return f"{salt}:{_derive_hash(password, salt)}"


def verify_password(stored_password, provided_password):
    (salt, hashed) = stored_password.split(':')
    return hashed == _derive_hash(provided_password, salt)


def create_user(username, password):
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(password)
    with _db_cursor() as c:
        c.execute(
            'INSERT INTO users (id, username, password, bio, theme) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, hashed_pw, '', 'light'),
        )
    return user_id


def get_user(username):
    with _db_cursor() as c:
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        return c.fetchone()


def update_bio(user_id, bio):
    sanitized_bio = escape(bio)
    with _db_cursor() as c:
        c.execute('UPDATE users SET bio=? WHERE id=?', (sanitized_bio, user_id))


def _set_user_cookie(username):
    response.set_cookie('user', username, secret=COOKIE_SECRET, httponly=True, secure=True)


def _form_credentials():
    username = escape(request.forms.get('username', '').strip())
    password = request.forms.get('password', '')
    return username, password


@app.route('/')
def index():
    return INDEX_HTML


@app.route('/register', method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        (username, password) = _form_credentials()
        if not username or not password:
            return 'Username and password are required'
        if get_user(username):
            return 'Username already exists'
        if len(password) < 8:
            return 'Password must be at least 8 characters'
        create_user(username, password)
        _set_user_cookie(username)
        return redirect('/profile')
    return REGISTER_HTML


@app.route('/login', method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        (username, password) = _form_credentials()
        user = get_user(username)
        if user and verify_password(user[2], password):
            _set_user_cookie(username)
            return redirect('/profile')
        return 'Invalid credentials'
    return LOGIN_HTML


@app.route('/profile', method=['GET', 'POST'])
def profile():
    username = request.get_cookie('user', secret=COOKIE_SECRET)
    if not username:
        return redirect('/login')
    user = get_user(username)
    if not user:
        return redirect('/login')
    if request.method == 'POST':
        new_bio = request.forms.get('bio', '')
        update_bio(user[0], new_bio)
        return redirect('/profile')
    return template(PROFILE_TEMPLATE, username=escape(username), bio=user[3])


@app.route('/logout')
def logout():
    response.delete_cookie('user')
    return redirect('/')


if __name__ == '__main__':
    run(app, host='localhost', port=8080, debug=False, reloader=False)
