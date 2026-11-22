from contextlib import contextmanager
import sqlite3
import uuid

from bottle import Bottle, run, request, response, template, redirect

app = Bottle()

DB_PATH = 'user_profiles.db'
COOKIE_NAME = 'user'
COOKIE_SECRET = 'weaksecret'
DEFAULT_BIO = ''
DEFAULT_THEME = 'light'

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

REGISTER_FORM_HTML = '''
        <h1>Register</h1>
        <form method="POST">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Register">
        </form>
    '''

LOGIN_FORM_HTML = '''
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

# Column indexes of the users table.
USER_ID = 0
USER_PASSWORD = 2
USER_BIO = 3


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

@contextmanager
def _db_cursor(commit=False):
    """Yield a cursor on the application database and always close it."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn.cursor()
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db():
    with _db_cursor(commit=True) as c:
        c.execute(CREATE_USERS_TABLE_SQL)


init_db()


def create_user(username, password):
    user_id = str(uuid.uuid4())
    with _db_cursor(commit=True) as c:
        c.execute(
            'INSERT INTO users (id, username, password, bio, theme) '
            'VALUES (?, ?, ?, ?, ?)',
            (user_id, username, password, DEFAULT_BIO, DEFAULT_THEME),
        )
    return user_id


def get_user(username):
    with _db_cursor() as c:
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        return c.fetchone()


def update_bio(user_id, bio):
    with _db_cursor(commit=True) as c:
        c.execute('UPDATE users SET bio=? WHERE id=?', (bio, user_id))


# --------------------------------------------------------------------------
# Session helpers
# --------------------------------------------------------------------------

def _start_session(username):
    response.set_cookie(COOKIE_NAME, username, secret=COOKIE_SECRET)


def _current_username():
    return request.get_cookie(COOKIE_NAME, secret=COOKIE_SECRET)


def _credentials_from_form():
    return request.forms.get('username'), request.forms.get('password')


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route('/')
def index():
    return INDEX_HTML


@app.route('/register', method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username, password = _credentials_from_form()
        if get_user(username):
            return 'Username already exists'
        create_user(username, password)
        _start_session(username)
        return redirect('/profile')
    return REGISTER_FORM_HTML


@app.route('/login', method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = _credentials_from_form()
        user = get_user(username)
        if user and user[USER_PASSWORD] == password:
            _start_session(username)
            return redirect('/profile')
        return 'Invalid credentials'
    return LOGIN_FORM_HTML


@app.route('/profile', method=['GET', 'POST'])
def profile():
    username = _current_username()
    if not username:
        return redirect('/login')
    user = get_user(username)
    if not user:
        return redirect('/login')
    if request.method == 'POST':
        new_bio = request.forms.get('bio')
        update_bio(user[USER_ID], new_bio)
        return redirect('/profile')
    return template(PROFILE_TEMPLATE, username=username, bio=user[USER_BIO])


@app.route('/logout')
def logout():
    response.delete_cookie(COOKIE_NAME)
    return redirect('/')


if __name__ == '__main__':
    run(app, host='localhost', port=8080, debug=True)
