from bottle import Bottle, run, request, response, template, redirect, abort
import sqlite3
import uuid
import hashlib
import secrets
from html import escape

app = Bottle()
COOKIE_SECRET = secrets.token_urlsafe(32)

DATABASE_PATH = 'user_profiles.db'
HASH_ALGORITHM = 'sha256'
PBKDF2_ITERATIONS = 100000

INDEX_PAGE = '''
        <h1>Welcome to MyApp</h1>
        <a href="/login">Login</a> | 
        <a href="/register">Register</a>
    '''

REGISTER_PAGE = '''
        <h1>Register</h1>
        <form method="POST">
            Username: <input type="text" name="username" required><br>
            Password: <input type="password" name="password" required minlength="8"><br>
            <input type="submit" value="Register">
        </form>
    '''

LOGIN_PAGE = '''
        <h1>Login</h1>
        <form method="POST">
            Username: <input type="text" name="username" required><br>
            Password: <input type="password" name="password" required><br>
            <input type="submit" value="Login">
        </form>
    '''

PROFILE_PAGE = '''
        <h1>Profile: {{username}}</h1>
        <div id="user-bio">{{!bio}}</div>
        <form method="POST">
            <textarea name="bio">{{bio}}</textarea><br>
            <input type="submit" value="Update Bio">
        </form>
        <a href="/logout">Logout</a>
    '''


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users\n                 (id TEXT PRIMARY KEY,\n                 username TEXT UNIQUE,\n                 password TEXT,\n                 bio TEXT,\n                 theme TEXT)')
    conn.commit()
    conn.close()


init_db()


def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM, password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return f"{salt}:{password_hash}"


def verify_password(stored_password, provided_password):
    (salt, hashed) = stored_password.split(':')
    new_hash = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM, provided_password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return hashed == new_hash


def create_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(password)
    c.execute(
        'INSERT INTO users (id, username, password, bio, theme) VALUES (?, ?, ?, ?, ?)',
        (user_id, username, hashed_pw, '', 'light'),
    )
    conn.commit()
    conn.close()
    return user_id


def get_user(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=?', (username,))
    user = c.fetchone()
    conn.close()
    return user


def update_bio(user_id, bio):
    sanitized_bio = escape(bio)
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET bio=? WHERE id=?', (sanitized_bio, user_id))
    conn.commit()
    conn.close()


def set_auth_cookie(username):
    response.set_cookie('user', username, secret=COOKIE_SECRET, httponly=True, secure=True)


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
        set_auth_cookie(username)
        return redirect('/profile')
    return REGISTER_PAGE


@app.route('/login', method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = escape(request.forms.get('username', '').strip())
        password = request.forms.get('password', '')
        user = get_user(username)
        if user and verify_password(user[2], password):
            set_auth_cookie(username)
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
    return template(PROFILE_PAGE, username=escape(username), bio=user[3])


@app.route('/logout')
def logout():
    response.delete_cookie('user')
    return redirect('/')


if __name__ == '__main__':
    run(app, host='localhost', port=8080, debug=False, reloader=False)
