import hashlib
import secrets
import sqlite3
import uuid
from contextlib import closing
from html import escape

from bottle import Bottle, run, request, response, template, redirect, abort

app = Bottle()
COOKIE_SECRET = secrets.token_urlsafe(32)

DB_PATH = 'user_profiles.db'
PBKDF2_ITERATIONS = 100000
SESSION_COOKIE = 'user'
MIN_PASSWORD_LENGTH = 8

INDEX_HTML = (
    '\n'
    '        <h1>Welcome to MyApp</h1>\n'
    '        <a href="/login">Login</a> | \n'
    '        <a href="/register">Register</a>\n'
    '    '
)

REGISTER_HTML = (
    '\n'
    '        <h1>Register</h1>\n'
    '        <form method="POST">\n'
    '            Username: <input type="text" name="username" required><br>\n'
    '            Password: <input type="password" name="password" required minlength="8"><br>\n'
    '            <input type="submit" value="Register">\n'
    '        </form>\n'
    '    '
)

LOGIN_HTML = (
    '\n'
    '        <h1>Login</h1>\n'
    '        <form method="POST">\n'
    '            Username: <input type="text" name="username" required><br>\n'
    '            Password: <input type="password" name="password" required><br>\n'
    '            <input type="submit" value="Login">\n'
    '        </form>\n'
    '    '
)

PROFILE_TEMPLATE = (
    '\n'
    '        <h1>Profile: {{username}}</h1>\n'
    '        <div id="user-bio">{{!bio}}</div>\n'
    '        <form method="POST">\n'
    '            <textarea name="bio">{{bio}}</textarea><br>\n'
    '            <input type="submit" value="Update Bio">\n'
    '        </form>\n'
    '        <a href="/logout">Logout</a>\n'
    '    '
)


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

def _connect():
    """Return a connection that is closed when the `with` block exits."""
    return closing(sqlite3.connect(DB_PATH))


def init_db():
    with _connect() as conn:
        c = conn.cursor()
        c.execute(
            'CREATE TABLE IF NOT EXISTS users\n'
            '                 (id TEXT PRIMARY KEY,\n'
            '                 username TEXT UNIQUE,\n'
            '                 password TEXT,\n'
            '                 bio TEXT,\n'
            '                 theme TEXT)'
        )
        conn.commit()


init_db()


# --------------------------------------------------------------------------
# Password handling
# --------------------------------------------------------------------------

def _derive_key(password, salt):
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()


def hash_password(password):
    salt = secrets.token_hex(16)
    return f"{salt}:{_derive_key(password, salt)}"


def verify_password(stored_password, provided_password):
    (salt, hashed) = stored_password.split(':')
    return hashed == _derive_key(provided_password, salt)


# --------------------------------------------------------------------------
# User data access
# --------------------------------------------------------------------------

def create_user(username, password):
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(password)
    with _connect() as conn:
        c = conn.cursor()
        c.execute(
            'INSERT INTO users (id, username, password, bio, theme) '
            'VALUES (?, ?, ?, ?, ?)',
            (user_id, username, hashed_pw, '', 'light'),
        )
        conn.commit()
    return user_id


def get_user(username):
    with _connect() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        return c.fetchone()


def update_bio(user_id, bio):
    sanitized_bio = escape(bio)
    with _connect() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET bio=? WHERE id=?', (sanitized_bio, user_id))
        conn.commit()


# --------------------------------------------------------------------------
# Request helpers
# --------------------------------------------------------------------------

def _read_credentials():
    """Return (escaped username, raw password) from the submitted form."""
    username = escape(request.forms.get('username', '').strip())
    password = request.forms.get('password', '')
    return username, password


def _start_session(username):
    response.set_cookie(
        SESSION_COOKIE, username, secret=COOKIE_SECRET, httponly=True, secure=True
    )


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route('/')
def index():
    return INDEX_HTML


@app.route('/register', method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username, password = _read_credentials()
        if not username or not password:
            return 'Username and password are required'
        if get_user(username):
            return 'Username already exists'
        if len(password) < MIN_PASSWORD_LENGTH:
            return 'Password must be at least 8 characters'
        create_user(username, password)
        _start_session(username)
        return redirect('/profile')
    return REGISTER_HTML


@app.route('/login', method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = _read_credentials()
        user = get_user(username)
        if user and verify_password(user[2], password):
            _start_session(username)
            return redirect('/profile')
        return 'Invalid credentials'
    return LOGIN_HTML


@app.route('/profile', method=['GET', 'POST'])
def profile():
    username = request.get_cookie(SESSION_COOKIE, secret=COOKIE_SECRET)
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
    response.delete_cookie(SESSION_COOKIE)
    return redirect('/')


if __name__ == '__main__':
    run(app, host='localhost', port=8080, debug=False, reloader=False)
