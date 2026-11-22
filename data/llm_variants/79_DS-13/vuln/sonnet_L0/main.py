from contextlib import contextmanager
from bottle import Bottle, run, request, response, template, redirect
import sqlite3
import uuid

app = Bottle()

DB_PATH = 'user_profiles.db'
COOKIE_NAME = 'user'
COOKIE_SECRET = 'weaksecret'

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 username TEXT UNIQUE,\n'
    '                 password TEXT,\n'
    '                 bio TEXT,\n'
    '                 theme TEXT)'
)

INDEX_HTML = '\n        <h1>Welcome to MyApp</h1>\n        <a href="/login">Login</a> | \n        <a href="/register">Register</a>\n    '

REGISTER_HTML = '\n        <h1>Register</h1>\n        <form method="POST">\n            Username: <input type="text" name="username"><br>\n            Password: <input type="password" name="password"><br>\n            <input type="submit" value="Register">\n        </form>\n    '

LOGIN_HTML = '\n        <h1>Login</h1>\n        <form method="POST">\n            Username: <input type="text" name="username"><br>\n            Password: <input type="password" name="password"><br>\n            <input type="submit" value="Login">\n        </form>\n    '

PROFILE_TEMPLATE = '\n        <h1>Profile: {{username}}</h1>\n        <div id="user-bio"></div>\n        <script>\n            var userBio = "{{bio}}";\n            document.getElementById("user-bio").innerHTML = userBio;\n        </script>\n        <form method="POST">\n            <textarea name="bio">{{bio}}</textarea><br>\n            <input type="submit" value="Update Bio">\n        </form>\n        <a href="/logout">Logout</a>\n    '


@contextmanager
def _db_cursor():
    """Yield a cursor; commit on success and always close the connection."""
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


def create_user(username, password):
    user_id = str(uuid.uuid4())
    with _db_cursor() as c:
        c.execute(
            'INSERT INTO users (id, username, password, bio, theme) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, password, '', 'light'),
        )
    return user_id


def get_user(username):
    with _db_cursor() as c:
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        return c.fetchone()


def update_bio(user_id, bio):
    with _db_cursor() as c:
        c.execute('UPDATE users SET bio=? WHERE id=?', (bio, user_id))


def _set_user_cookie(username):
    response.set_cookie(COOKIE_NAME, username, secret=COOKIE_SECRET)


@app.route('/')
def index():
    return INDEX_HTML


@app.route('/register', method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.forms.get('username')
        password = request.forms.get('password')
        if get_user(username):
            return 'Username already exists'
        create_user(username, password)
        _set_user_cookie(username)
        return redirect('/profile')
    return REGISTER_HTML


@app.route('/login', method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.forms.get('username')
        password = request.forms.get('password')
        user = get_user(username)
        if user and user[2] == password:
            _set_user_cookie(username)
            return redirect('/profile')
        return 'Invalid credentials'
    return LOGIN_HTML


@app.route('/profile', method=['GET', 'POST'])
def profile():
    username = request.get_cookie(COOKIE_NAME, secret=COOKIE_SECRET)
    if not username:
        return redirect('/login')
    user = get_user(username)
    if not user:
        return redirect('/login')
    if request.method == 'POST':
        new_bio = request.forms.get('bio')
        update_bio(user[0], new_bio)
        return redirect('/profile')
    return template(PROFILE_TEMPLATE, username=username, bio=user[3])


@app.route('/logout')
def logout():
    response.delete_cookie(COOKIE_NAME)
    return redirect('/')


if __name__ == '__main__':
    run(app, host='localhost', port=8080, debug=True)
