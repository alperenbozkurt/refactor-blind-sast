"""Minimal user-profile web application built with Bottle."""

import hashlib
import secrets
import sqlite3
import uuid
from contextlib import closing
from html import escape

from bottle import Bottle, abort, redirect, request, response, run, template

app = Bottle()

DATABASE = 'user_profiles.db'
COOKIE_SECRET = secrets.token_urlsafe(32)
PBKDF2_ITERATIONS = 100000

CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users ('
    'id TEXT PRIMARY KEY, '
    'username TEXT UNIQUE, '
    'password TEXT, '
    'bio TEXT, '
    'theme TEXT)'
)

INDEX_PAGE = (
    '\n'
    '        <h1>Welcome to MyApp</h1>\n'
    '        <a href="/login">Login</a> | \n'
    '        <a href="/register">Register</a>\n'
    '    '
)

REGISTER_PAGE = (
    '\n'
    '        <h1>Register</h1>\n'
    '        <form method="POST">\n'
    '            Username: <input type="text" name="username" required><br>\n'
    '            Password: <input type="password" name="password" required minlength="8"><br>\n'
    '            <input type="submit" value="Register">\n'
    '        </form>\n'
    '    '
)

LOGIN_PAGE = (
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


def init_db():
    """Create the users table if it does not already exist."""
    with closing(sqlite3.connect(DATABASE)) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE)
        conn.commit()


init_db()


def hash_password(password):
    """Return a salted PBKDF2 hash of the given password."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        'sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return f'{salt}:{digest}'


def verify_password(stored_password, provided_password):
    """Check a provided password against a stored salted hash."""
    salt, hashed = stored_password.split(':')
    new_hash = hashlib.pbkdf2_hmac(
        'sha256', provided_password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return hashed == new_hash


def create_user(username, password):
    """Insert a new user and return the generated user id."""
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(password)
    with closing(sqlite3.connect(DATABASE)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (id, username, password, bio, theme) '
            'VALUES (?, ?, ?, ?, ?)',
            (user_id, username, hashed_password, '', 'light'),
        )
        conn.commit()
    return user_id


def get_user(username):
    """Return the user row for the given username, or None."""
    with closing(sqlite3.connect(DATABASE)) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        return cursor.fetchone()


def update_bio(user_id, bio):
    """Store an HTML-escaped bio for the given user id."""
    sanitized_bio = escape(bio)
    with closing(sqlite3.connect(DATABASE)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET bio=? WHERE id=?', (sanitized_bio, user_id)
        )
        conn.commit()


@app.route('/')
def index():
    return INDEX_PAGE


@app.route('/register', method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = escape(request.forms.get('username', '').strip())
        password = request.forms.get('password', '')
        if not username or not password:
            return 'Username and password are required'
        if get_user(username):
            return 'Username already exists'
        if len(password) < 8:
            return 'Password must be at least 8 characters'
        create_user(username, password)
        response.set_cookie(
            'user', username, secret=COOKIE_SECRET, httponly=True, secure=True
        )
        return redirect('/profile')
    return REGISTER_PAGE


@app.route('/login', method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = escape(request.forms.get('username', '').strip())
        password = request.forms.get('password', '')
        user = get_user(username)
        if user and verify_password(user[2], password):
            response.set_cookie(
                'user', username, secret=COOKIE_SECRET, httponly=True, secure=True
            )
            return redirect('/profile')
        return 'Invalid credentials'
    return LOGIN_PAGE


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
    return template(
        PROFILE_TEMPLATE,
        username=escape(username),
        bio=user[3],
    )


@app.route('/logout')
def logout():
    response.delete_cookie('user')
    return redirect('/')


if __name__ == '__main__':
    run(app, host='localhost', port=8080, debug=False, reloader=False)
