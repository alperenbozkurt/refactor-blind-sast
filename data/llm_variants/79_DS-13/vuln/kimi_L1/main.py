from bottle import Bottle, run, request, response, template, redirect
import sqlite3
import uuid

app = Bottle()

DATABASE_PATH = 'user_profiles.db'

COOKIE_NAME = 'user'
COOKIE_SECRET = 'weaksecret'

DEFAULT_BIO = ''
DEFAULT_THEME = 'light'

CREATE_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 username TEXT UNIQUE,\n'
    '                 password TEXT,\n'
    '                 bio TEXT,\n'
    '                 theme TEXT)'
)
INSERT_USER_SQL = (
    'INSERT INTO users (id, username, password, bio, theme) '
    'VALUES (?, ?, ?, ?, ?)'
)
SELECT_USER_SQL = 'SELECT * FROM users WHERE username=?'
UPDATE_BIO_SQL = 'UPDATE users SET bio=? WHERE id=?'

INDEX_PAGE = """
        <h1>Welcome to MyApp</h1>
        <a href="/login">Login</a> | 
        <a href="/register">Register</a>
    """

REGISTER_PAGE = """
        <h1>Register</h1>
        <form method="POST">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Register">
        </form>
    """

LOGIN_PAGE = """
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


def _connect():
    """Open a new connection to the application database."""
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    """Create the users table if it does not already exist."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    conn.close()


init_db()


def create_user(username, password):
    """Insert a new user with the default bio and theme; return its id."""
    conn = _connect()
    cursor = conn.cursor()
    user_id = str(uuid.uuid4())
    cursor.execute(
        INSERT_USER_SQL,
        (user_id, username, password, DEFAULT_BIO, DEFAULT_THEME),
    )
    conn.commit()
    conn.close()
    return user_id


def get_user(username):
    """Return the users row for username, or None if there is no match."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(SELECT_USER_SQL, (username,))
    user = cursor.fetchone()
    conn.close()
    return user


def update_bio(user_id, bio):
    """Set the bio of the user with the given id."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(UPDATE_BIO_SQL, (bio, user_id))
    conn.commit()
    conn.close()


@app.route('/')
def index():
    return INDEX_PAGE


@app.route('/register', method=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.forms.get('username')
        password = request.forms.get('password')
        if get_user(username):
            return 'Username already exists'
        create_user(username, password)
        response.set_cookie(COOKIE_NAME, username, secret=COOKIE_SECRET)
        return redirect('/profile')
    return REGISTER_PAGE


@app.route('/login', method=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.forms.get('username')
        password = request.forms.get('password')
        user = get_user(username)
        if user:
            stored_password = user[2]
            if stored_password == password:
                response.set_cookie(COOKIE_NAME, username, secret=COOKIE_SECRET)
                return redirect('/profile')
        return 'Invalid credentials'
    return LOGIN_PAGE


@app.route('/profile', method=['GET', 'POST'])
def profile():
    username = request.get_cookie(COOKIE_NAME, secret=COOKIE_SECRET)
    if not username:
        return redirect('/login')
    user = get_user(username)
    if not user:
        return redirect('/login')
    user_id, _, _, bio, _ = user
    if request.method == 'POST':
        new_bio = request.forms.get('bio')
        update_bio(user_id, new_bio)
        return redirect('/profile')
    return template(PROFILE_TEMPLATE, username=username, bio=bio)


@app.route('/logout')
def logout():
    response.delete_cookie(COOKIE_NAME)
    return redirect('/')


if __name__ == '__main__':
    run(app, host='localhost', port=8080, debug=True)
