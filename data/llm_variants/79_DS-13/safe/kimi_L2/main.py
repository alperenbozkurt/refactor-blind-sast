"""User profile web application built with Bottle and SQLite.

Refactored for modularity: configuration is centralised in ``Config``,
SQL statements, HTML templates and user-facing messages are named
constants, and small private helpers remove duplication between routes.
"""

from bottle import Bottle, run, request, response, template, redirect, abort
import sqlite3
import uuid
import hashlib
import secrets
from html import escape


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Application-wide configuration constants."""

    DATABASE_PATH = 'user_profiles.db'

    # Password hashing
    HASH_ALGORITHM = 'sha256'
    PBKDF2_ITERATIONS = 100000
    SALT_LENGTH = 16
    HASH_SEPARATOR = ':'

    # Validation rules and record defaults
    MIN_PASSWORD_LENGTH = 8
    DEFAULT_BIO = ''
    DEFAULT_THEME = 'light'

    # Session cookie
    SESSION_COOKIE_NAME = 'user'

    # Development server
    HOST = 'localhost'
    PORT = 8080
    DEBUG = False
    RELOADER = False


# SQL statements
SQL_CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 username TEXT UNIQUE,\n'
    '                 password TEXT,\n'
    '                 bio TEXT,\n'
    '                 theme TEXT)'
)
SQL_INSERT_USER = (
    'INSERT INTO users (id, username, password, bio, theme) '
    'VALUES (?, ?, ?, ?, ?)'
)
SQL_SELECT_USER_BY_USERNAME = 'SELECT * FROM users WHERE username=?'
SQL_UPDATE_BIO = 'UPDATE users SET bio=? WHERE id=?'

# Column indexes for rows returned by get_user()
USER_COL_ID = 0
USER_COL_USERNAME = 1
USER_COL_PASSWORD = 2
USER_COL_BIO = 3
USER_COL_THEME = 4

# Form field names
FORM_USERNAME = 'username'
FORM_PASSWORD = 'password'
FORM_BIO = 'bio'

# Route paths
PATH_HOME = '/'
PATH_REGISTER = '/register'
PATH_LOGIN = '/login'
PATH_PROFILE = '/profile'
PATH_LOGOUT = '/logout'

# User-facing messages
MSG_CREDENTIALS_REQUIRED = 'Username and password are required'
MSG_USERNAME_EXISTS = 'Username already exists'
MSG_PASSWORD_TOO_SHORT = 'Password must be at least 8 characters'
MSG_INVALID_CREDENTIALS = 'Invalid credentials'

# Page templates
INDEX_TEMPLATE = (
    '\n'
    '        <h1>Welcome to MyApp</h1>\n'
    '        <a href="/login">Login</a> | \n'
    '        <a href="/register">Register</a>\n'
    '    '
)
REGISTER_TEMPLATE = (
    '\n'
    '        <h1>Register</h1>\n'
    '        <form method="POST">\n'
    '            Username: <input type="text" name="username" required><br>\n'
    '            Password: <input type="password" name="password" required minlength="8"><br>\n'
    '            <input type="submit" value="Register">\n'
    '        </form>\n'
    '    '
)
LOGIN_TEMPLATE = (
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


app = Bottle()
COOKIE_SECRET = secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _connect():
    """Return a new connection to the application database."""
    return sqlite3.connect(Config.DATABASE_PATH)


def init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute(SQL_CREATE_USERS_TABLE)
    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password):
    salt = secrets.token_hex(Config.SALT_LENGTH)
    digest = hashlib.pbkdf2_hmac(
        Config.HASH_ALGORITHM,
        password.encode(),
        salt.encode(),
        Config.PBKDF2_ITERATIONS,
    ).hex()
    return f"{salt}{Config.HASH_SEPARATOR}{digest}"


def verify_password(stored_password, provided_password):
    salt, hashed = stored_password.split(Config.HASH_SEPARATOR)
    new_hash = hashlib.pbkdf2_hmac(
        Config.HASH_ALGORITHM,
        provided_password.encode(),
        salt.encode(),
        Config.PBKDF2_ITERATIONS,
    ).hex()
    return hashed == new_hash


# ---------------------------------------------------------------------------
# User persistence
# ---------------------------------------------------------------------------

def create_user(username, password):
    conn = _connect()
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(password)
    c.execute(
        SQL_INSERT_USER,
        (user_id, username, hashed_pw, Config.DEFAULT_BIO, Config.DEFAULT_THEME),
    )
    conn.commit()
    conn.close()
    return user_id


def get_user(username):
    conn = _connect()
    c = conn.cursor()
    c.execute(SQL_SELECT_USER_BY_USERNAME, (username,))
    user = c.fetchone()
    conn.close()
    return user


def update_bio(user_id, bio):
    sanitized_bio = escape(bio)
    conn = _connect()
    c = conn.cursor()
    c.execute(SQL_UPDATE_BIO, (sanitized_bio, user_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------

def _posted_credentials():
    username = escape(request.forms.get(FORM_USERNAME, '').strip())
    password = request.forms.get(FORM_PASSWORD, '')
    return username, password


def _set_session_cookie(username):
    response.set_cookie(
        Config.SESSION_COOKIE_NAME,
        username,
        secret=COOKIE_SECRET,
        httponly=True,
        secure=True,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route(PATH_HOME)
def index():
    return INDEX_TEMPLATE


@app.route(PATH_REGISTER, method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username, password = _posted_credentials()
        if not username or not password:
            return MSG_CREDENTIALS_REQUIRED
        if get_user(username):
            return MSG_USERNAME_EXISTS
        if len(password) < Config.MIN_PASSWORD_LENGTH:
            return MSG_PASSWORD_TOO_SHORT
        create_user(username, password)
        _set_session_cookie(username)
        return redirect(PATH_PROFILE)
    return REGISTER_TEMPLATE


@app.route(PATH_LOGIN, method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = _posted_credentials()
        user = get_user(username)
        if user and verify_password(user[USER_COL_PASSWORD], password):
            _set_session_cookie(username)
            return redirect(PATH_PROFILE)
        return MSG_INVALID_CREDENTIALS
    return LOGIN_TEMPLATE


@app.route(PATH_PROFILE, method=['GET', 'POST'])
def profile():
    username = request.get_cookie(Config.SESSION_COOKIE_NAME, secret=COOKIE_SECRET)
    if not username:
        return redirect(PATH_LOGIN)
    user = get_user(username)
    if not user:
        return redirect(PATH_LOGIN)
    if request.method == 'POST':
        new_bio = request.forms.get(FORM_BIO, '')
        update_bio(user[USER_COL_ID], new_bio)
        return redirect(PATH_PROFILE)
    return template(PROFILE_TEMPLATE, username=escape(username), bio=user[USER_COL_BIO])


@app.route(PATH_LOGOUT)
def logout():
    response.delete_cookie(Config.SESSION_COOKIE_NAME)
    return redirect(PATH_HOME)


if __name__ == '__main__':
    run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, reloader=Config.RELOADER)
