from bottle import Bottle, run, request, response, template, redirect, abort
import sqlite3
import uuid
import hashlib
import secrets
from contextlib import closing, contextmanager
from html import escape

# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------
DB_PATH = 'user_profiles.db'

SALT_BYTES = 16
PBKDF2_ALGORITHM = 'sha256'
PBKDF2_ITERATIONS = 100000
PASSWORD_SEPARATOR = ':'
MIN_PASSWORD_LENGTH = 8

COOKIE_NAME = 'user'
COOKIE_SECRET_BYTES = 32

DEFAULT_BIO = ''
DEFAULT_THEME = 'light'

HOST = 'localhost'
PORT = 8080

ROUTE_INDEX = '/'
ROUTE_REGISTER = '/register'
ROUTE_LOGIN = '/login'
ROUTE_PROFILE = '/profile'
ROUTE_LOGOUT = '/logout'
GET_POST = ['GET', 'POST']

# User row column indexes (SELECT * FROM users)
COL_ID = 0
COL_USERNAME = 1
COL_PASSWORD = 2
COL_BIO = 3
COL_THEME = 4

# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------
MSG_CREDENTIALS_REQUIRED = 'Username and password are required'
MSG_USERNAME_EXISTS = 'Username already exists'
MSG_PASSWORD_TOO_SHORT = 'Password must be at least 8 characters'
MSG_INVALID_CREDENTIALS = 'Invalid credentials'

# --------------------------------------------------------------------------
# SQL statements
# --------------------------------------------------------------------------
SQL_CREATE_USERS = (
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
SQL_SELECT_USER = 'SELECT * FROM users WHERE username=?'
SQL_UPDATE_BIO = 'UPDATE users SET bio=? WHERE id=?'

# --------------------------------------------------------------------------
# HTML templates
# --------------------------------------------------------------------------
INDEX_HTML = '''
        <h1>Welcome to MyApp</h1>
        <a href="/login">Login</a> | 
        <a href="/register">Register</a>
    '''

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

app = Bottle()
COOKIE_SECRET = secrets.token_urlsafe(COOKIE_SECRET_BYTES)


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
@contextmanager
def _db_cursor(commit=False):
    """Yield a cursor on a fresh connection, optionally committing, and always closing."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()


def init_db():
    with _db_cursor(commit=True) as c:
        c.execute(SQL_CREATE_USERS)


init_db()


# --------------------------------------------------------------------------
# Password helpers
# --------------------------------------------------------------------------
def _derive_key(password, salt):
    return hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM, password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()


def hash_password(password):
    salt = secrets.token_hex(SALT_BYTES)
    return f"{salt}{PASSWORD_SEPARATOR}{_derive_key(password, salt)}"


def verify_password(stored_password, provided_password):
    (salt, hashed) = stored_password.split(PASSWORD_SEPARATOR)
    return hashed == _derive_key(provided_password, salt)


# --------------------------------------------------------------------------
# User data access
# --------------------------------------------------------------------------
def create_user(username, password):
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(password)
    with _db_cursor(commit=True) as c:
        c.execute(
            SQL_INSERT_USER,
            (user_id, username, hashed_pw, DEFAULT_BIO, DEFAULT_THEME),
        )
    return user_id


def get_user(username):
    with _db_cursor() as c:
        c.execute(SQL_SELECT_USER, (username,))
        return c.fetchone()


def update_bio(user_id, bio):
    sanitized_bio = escape(bio)
    with _db_cursor(commit=True) as c:
        c.execute(SQL_UPDATE_BIO, (sanitized_bio, user_id))


# --------------------------------------------------------------------------
# Request / response helpers
# --------------------------------------------------------------------------
def _read_credentials():
    username = escape(request.forms.get('username', '').strip())
    password = request.forms.get('password', '')
    return username, password


def _set_session_cookie(username):
    response.set_cookie(
        COOKIE_NAME, username, secret=COOKIE_SECRET, httponly=True, secure=True
    )


def _current_username():
    return request.get_cookie(COOKIE_NAME, secret=COOKIE_SECRET)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route(ROUTE_INDEX)
def index():
    return INDEX_HTML


@app.route(ROUTE_REGISTER, method=GET_POST)
def register():
    if request.method == 'POST':
        (username, password) = _read_credentials()
        if not username or not password:
            return MSG_CREDENTIALS_REQUIRED
        if get_user(username):
            return MSG_USERNAME_EXISTS
        if len(password) < MIN_PASSWORD_LENGTH:
            return MSG_PASSWORD_TOO_SHORT
        create_user(username, password)
        _set_session_cookie(username)
        return redirect(ROUTE_PROFILE)
    return REGISTER_HTML


@app.route(ROUTE_LOGIN, method=GET_POST)
def login():
    if request.method == 'POST':
        (username, password) = _read_credentials()
        user = get_user(username)
        if user and verify_password(user[COL_PASSWORD], password):
            _set_session_cookie(username)
            return redirect(ROUTE_PROFILE)
        return MSG_INVALID_CREDENTIALS
    return LOGIN_HTML


@app.route(ROUTE_PROFILE, method=GET_POST)
def profile():
    username = _current_username()
    if not username:
        return redirect(ROUTE_LOGIN)
    user = get_user(username)
    if not user:
        return redirect(ROUTE_LOGIN)
    if request.method == 'POST':
        new_bio = request.forms.get('bio', '')
        update_bio(user[COL_ID], new_bio)
        return redirect(ROUTE_PROFILE)
    return template(PROFILE_TEMPLATE, username=escape(username), bio=user[COL_BIO])


@app.route(ROUTE_LOGOUT)
def logout():
    response.delete_cookie(COOKIE_NAME)
    return redirect(ROUTE_INDEX)


if __name__ == '__main__':
    run(app, host=HOST, port=PORT, debug=False, reloader=False)
