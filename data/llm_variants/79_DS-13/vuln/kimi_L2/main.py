"""MyApp - a small user-profile web application.

Provides user registration, login and editable profile pages backed by a
SQLite database, served with the Bottle web framework.
"""

import sqlite3
import uuid
from contextlib import closing

from bottle import Bottle, run, request, response, template, redirect


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Application-wide configuration values."""

    DATABASE_PATH = 'user_profiles.db'
    COOKIE_NAME = 'user'
    COOKIE_SECRET = 'weaksecret'
    DEFAULT_BIO = ''
    DEFAULT_THEME = 'light'
    SERVER_HOST = 'localhost'
    SERVER_PORT = 8080
    DEBUG = True


# ---------------------------------------------------------------------------
# Routes and user-facing messages
# ---------------------------------------------------------------------------

ROUTE_INDEX = '/'
ROUTE_REGISTER = '/register'
ROUTE_LOGIN = '/login'
ROUTE_PROFILE = '/profile'
ROUTE_LOGOUT = '/logout'

MESSAGE_USERNAME_TAKEN = 'Username already exists'
MESSAGE_INVALID_CREDENTIALS = 'Invalid credentials'


# ---------------------------------------------------------------------------
# SQL statements and users-table column indices
# ---------------------------------------------------------------------------

# Indices of the columns in rows returned by "SELECT * FROM users".
COL_ID = 0
COL_USERNAME = 1
COL_PASSWORD = 2
COL_BIO = 3
COL_THEME = 4

CREATE_USERS_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS users
        (id TEXT PRIMARY KEY,
         username TEXT UNIQUE,
         password TEXT,
         bio TEXT,
         theme TEXT)
'''

INSERT_USER_SQL = (
    'INSERT INTO users (id, username, password, bio, theme) '
    'VALUES (?, ?, ?, ?, ?)'
)
SELECT_USER_BY_USERNAME_SQL = 'SELECT * FROM users WHERE username=?'
UPDATE_USER_BIO_SQL = 'UPDATE users SET bio=? WHERE id=?'


# ---------------------------------------------------------------------------
# Page templates
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = (
    '\n'
    '        <h1>Welcome to MyApp</h1>\n'
    '        <a href="/login">Login</a> | \n'
    '        <a href="/register">Register</a>\n'
    '    '
)

REGISTER_TEMPLATE = '''
        <h1>Register</h1>
        <form method="POST">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Register">
        </form>
    '''

LOGIN_TEMPLATE = '''
        <h1>Login</h1>
        <form method="POST">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
        </form>
    '''

PROFILE_TEMPLATE = '''
        <h1>Profile: {{username}}</h1>
        <div id="user-bio"></div>
        <script>
            var userBio = "{{bio}}";
            document.getElementById("user-bio").innerHTML = userBio;
        </script>
        <form method="POST">
            <textarea name="bio">{{bio}}</textarea><br>
            <input type="submit" value="Update Bio">
        </form>
        <a href="/logout">Logout</a>
    '''


app = Bottle()


# ---------------------------------------------------------------------------
# Database access layer
# ---------------------------------------------------------------------------

def _connect():
    """Open a new connection to the application database."""
    return sqlite3.connect(Config.DATABASE_PATH)


def init_db():
    """Create the users table if it does not already exist."""
    with closing(_connect()) as conn:
        with conn:
            conn.execute(CREATE_USERS_TABLE_SQL)


init_db()


def create_user(username, password):
    """Insert a new user with the default bio and theme; return its id."""
    user_id = str(uuid.uuid4())
    with closing(_connect()) as conn:
        with conn:
            conn.execute(INSERT_USER_SQL, (user_id, username, password,
                                           Config.DEFAULT_BIO,
                                           Config.DEFAULT_THEME))
    return user_id


def get_user(username):
    """Return the users row for *username*, or None if it does not exist."""
    with closing(_connect()) as conn:
        cursor = conn.execute(SELECT_USER_BY_USERNAME_SQL, (username,))
        return cursor.fetchone()


def update_bio(user_id, bio):
    """Set the bio of the user identified by *user_id*."""
    with closing(_connect()) as conn:
        with conn:
            conn.execute(UPDATE_USER_BIO_SQL, (bio, user_id))


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _session_username():
    """Return the username stored in the signed session cookie, if any."""
    return request.get_cookie(Config.COOKIE_NAME, secret=Config.COOKIE_SECRET)


def _set_session_cookie(username):
    """Store *username* in the signed session cookie."""
    response.set_cookie(Config.COOKIE_NAME, username,
                        secret=Config.COOKIE_SECRET)


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------

@app.route(ROUTE_INDEX)
def index():
    return INDEX_TEMPLATE


@app.route(ROUTE_REGISTER, method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.forms.get('username')
        password = request.forms.get('password')
        if get_user(username):
            return MESSAGE_USERNAME_TAKEN
        create_user(username, password)
        _set_session_cookie(username)
        return redirect(ROUTE_PROFILE)
    return REGISTER_TEMPLATE


@app.route(ROUTE_LOGIN, method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.forms.get('username')
        password = request.forms.get('password')
        user = get_user(username)
        if user and user[COL_PASSWORD] == password:
            _set_session_cookie(username)
            return redirect(ROUTE_PROFILE)
        return MESSAGE_INVALID_CREDENTIALS
    return LOGIN_TEMPLATE


@app.route(ROUTE_PROFILE, method=['GET', 'POST'])
def profile():
    username = _session_username()
    if not username:
        return redirect(ROUTE_LOGIN)
    user = get_user(username)
    if not user:
        return redirect(ROUTE_LOGIN)
    if request.method == 'POST':
        new_bio = request.forms.get('bio')
        update_bio(user[COL_ID], new_bio)
        return redirect(ROUTE_PROFILE)
    return template(PROFILE_TEMPLATE, username=username, bio=user[COL_BIO])


@app.route(ROUTE_LOGOUT)
def logout():
    response.delete_cookie(Config.COOKIE_NAME)
    return redirect(ROUTE_INDEX)


if __name__ == '__main__':
    run(app, host=Config.SERVER_HOST, port=Config.SERVER_PORT,
        debug=Config.DEBUG)
