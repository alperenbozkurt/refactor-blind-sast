from contextlib import closing, contextmanager
from dataclasses import dataclass

from bottle import Bottle, run, request, response, template, redirect
import sqlite3
import uuid


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DatabaseConfig:
    path: str = 'user_profiles.db'


@dataclass(frozen=True)
class ServerConfig:
    host: str = 'localhost'
    port: int = 8080
    debug: bool = True


@dataclass(frozen=True)
class AuthConfig:
    cookie_name: str = 'user'
    cookie_secret: str = 'weaksecret'


DB_CONFIG = DatabaseConfig()
SERVER_CONFIG = ServerConfig()
AUTH_CONFIG = AuthConfig()

DEFAULT_BIO = ''
DEFAULT_THEME = 'light'

# Column positions in the ``users`` table (SELECT * order).
COL_ID = 0
COL_USERNAME = 1
COL_PASSWORD = 2
COL_BIO = 3
COL_THEME = 4

# Routes
ROUTE_INDEX = '/'
ROUTE_REGISTER = '/register'
ROUTE_LOGIN = '/login'
ROUTE_PROFILE = '/profile'
ROUTE_LOGOUT = '/logout'
FORM_METHODS = ['GET', 'POST']

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Response messages and page templates
# ---------------------------------------------------------------------------

MSG_USERNAME_EXISTS = 'Username already exists'
MSG_INVALID_CREDENTIALS = 'Invalid credentials'

INDEX_HTML = """
        <h1>Welcome to MyApp</h1>
        <a href="/login">Login</a> | 
        <a href="/register">Register</a>
    """

REGISTER_HTML = """
        <h1>Register</h1>
        <form method="POST">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Register">
        </form>
    """

LOGIN_HTML = """
        <h1>Login</h1>
        <form method="POST">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
        </form>
    """

PROFILE_TEMPLATE = """
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
    """

app = Bottle()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def _cursor(commit=False):
    """Open a connection, yield a cursor, optionally commit, always close."""
    with closing(sqlite3.connect(DB_CONFIG.path)) as conn:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()


def init_db():
    with _cursor(commit=True) as c:
        c.execute(SQL_CREATE_USERS_TABLE)


init_db()


def create_user(username, password):
    user_id = str(uuid.uuid4())
    with _cursor(commit=True) as c:
        c.execute(
            SQL_INSERT_USER,
            (user_id, username, password, DEFAULT_BIO, DEFAULT_THEME),
        )
    return user_id


def get_user(username):
    with _cursor() as c:
        c.execute(SQL_SELECT_USER_BY_USERNAME, (username,))
        return c.fetchone()


def update_bio(user_id, bio):
    with _cursor(commit=True) as c:
        c.execute(SQL_UPDATE_BIO, (bio, user_id))


# ---------------------------------------------------------------------------
# Request / session helpers
# ---------------------------------------------------------------------------

def _get_credentials():
    return request.forms.get('username'), request.forms.get('password')


def _set_session(username):
    response.set_cookie(
        AUTH_CONFIG.cookie_name, username, secret=AUTH_CONFIG.cookie_secret
    )


def _get_session_username():
    return request.get_cookie(
        AUTH_CONFIG.cookie_name, secret=AUTH_CONFIG.cookie_secret
    )


def _clear_session():
    response.delete_cookie(AUTH_CONFIG.cookie_name)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route(ROUTE_INDEX)
def index():
    return INDEX_HTML


@app.route(ROUTE_REGISTER, method=FORM_METHODS)
def register():
    if request.method == 'POST':
        username, password = _get_credentials()
        if get_user(username):
            return MSG_USERNAME_EXISTS
        create_user(username, password)
        _set_session(username)
        return redirect(ROUTE_PROFILE)
    return REGISTER_HTML


@app.route(ROUTE_LOGIN, method=FORM_METHODS)
def login():
    if request.method == 'POST':
        username, password = _get_credentials()
        user = get_user(username)
        if user and user[COL_PASSWORD] == password:
            _set_session(username)
            return redirect(ROUTE_PROFILE)
        return MSG_INVALID_CREDENTIALS
    return LOGIN_HTML


@app.route(ROUTE_PROFILE, method=FORM_METHODS)
def profile():
    username = _get_session_username()
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
    _clear_session()
    return redirect(ROUTE_INDEX)


if __name__ == '__main__':
    run(
        app,
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )
