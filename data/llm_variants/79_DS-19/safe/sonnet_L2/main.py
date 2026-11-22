from sanic import Sanic
from sanic.response import html
from sanic.exceptions import NotFound
import aiosqlite
import uuid
from datetime import datetime
import html as html_escape
import json
import secrets

# --------------------------------------------------------------------------- #
# Constants / configuration
# --------------------------------------------------------------------------- #

APP_NAME = 'ProfileApp'
DB_PATH = 'profiles.db'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SERVER_DEBUG = False

SECRET_KEY_BYTES = 32

ALLOWED_THEMES = ['light', 'dark']
DEFAULT_THEME = 'light'

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'",
}

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                          (id TEXT PRIMARY KEY,\n'
    '                          username TEXT UNIQUE,\n'
    '                          full_name TEXT,\n'
    '                          bio TEXT,\n'
    '                          created_at TEXT)'
)
INSERT_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
SELECT_USER_SQL = 'SELECT * FROM users WHERE username = ?'

# Column indexes of the ``users`` table.
COL_ID = 0
COL_USERNAME = 1
COL_FULL_NAME = 2
COL_BIO = 3
COL_CREATED_AT = 4

MSG_USERNAME_REQUIRED = 'Username parameter is required'
MSG_USER_NOT_FOUND = 'User not found'
MSG_CREATE_FIELDS_REQUIRED = 'Username and full name are required'

# --------------------------------------------------------------------------- #
# HTML templates
# --------------------------------------------------------------------------- #

INDEX_PAGE = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Profile System</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .profile { border: 1px solid #ddd; padding: 20px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>Profile System</h1>
            <form action="/profile" method="GET">
                <input type="text" name="username" placeholder="Enter username" required>
                <button type="submit">View Profile</button>
            </form>
            <p>Try usernames: alice, bob, charlie</p>
        </body>
        </html>
    '''

CREATE_FORM_PAGE = '''
        <h1>Create Profile</h1>
        <form method="POST">
            <p>
                <label>Username:</label><br>
                <input type="text" name="username" required maxlength="50">
            </p>
            <p>
                <label>Full Name:</label><br>
                <input type="text" name="full_name" required maxlength="100">
            </p>
            <p>
                <label>Bio:</label><br>
                <textarea name="bio" rows="4" maxlength="500"></textarea>
            </p>
            <button type="submit">Create Profile</button>
        </form>
    '''


def render_profile_page(user, safe_user_data):
    """Render the HTML profile page for a user row."""
    escape = html_escape.escape
    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{escape(user[COL_USERNAME])}'s Profile</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}
                .dark {{ background: #333; color: white; }}
            </style>
        </head>
        <body id="body">
            <div class="profile">
                <h1>{escape(user[COL_FULL_NAME])}</h1>
                <p>@{escape(user[COL_USERNAME])}</p>
                <div id="bio">{escape(user[COL_BIO])}</div>
                <p><small>Joined: {escape(user[COL_CREATED_AT])}</small></p>
            </div>
            <a href="/">Back to home</a>
            
            <script>
                // Safely apply theme
                const userData = {json.dumps(safe_user_data)};
                document.getElementById("body").className = userData.theme;
                
                // Safe way to handle URL parameters
                const urlParams = new URLSearchParams(window.location.search);
                const welcomeMessage = urlParams.get('welcome') || 'Welcome to my profile!';
                
                // Safely add content to DOM
                const bioElement = document.getElementById("bio");
                const welcomePara = document.createElement('p');
                welcomePara.innerHTML = '<em>' + document.createTextNode(welcomeMessage).textContent + '</em>';
                bioElement.appendChild(welcomePara);
            </script>
        </body>
        </html>
    """


def render_profile_created(username):
    """Render the confirmation message after a profile is created."""
    return (
        f"Profile created! <a href='/profile?username="
        f"{html_escape.escape(username)}'>View profile</a>"
    )


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

app = Sanic(APP_NAME)
app.config.SECRET = secrets.token_urlsafe(SECRET_KEY_BYTES)


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_USERS_TABLE_SQL)
        await db.commit()


@app.listener('before_server_start')
async def setup_db(app, loop):
    await init_db()


def _sanitize(value):
    return html_escape.escape(value)


def _new_user_id():
    return str(uuid.uuid4())


async def create_user(username, full_name, bio):
    sanitized_username = _sanitize(username)
    sanitized_full_name = _sanitize(full_name)
    sanitized_bio = _sanitize(bio)
    user_id = _new_user_id()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            INSERT_USER_SQL,
            (
                user_id,
                sanitized_username,
                sanitized_full_name,
                sanitized_bio,
                datetime.now().isoformat(),
            ),
        )
        await db.commit()
    return user_id


async def get_user(username):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(SELECT_USER_SQL, (username,))
        return await cursor.fetchone()


# --------------------------------------------------------------------------- #
# Request helpers
# --------------------------------------------------------------------------- #

def _resolve_theme(request):
    theme = request.args.get('theme', DEFAULT_THEME)
    if theme not in ALLOWED_THEMES:
        theme = DEFAULT_THEME
    return theme


def _build_safe_user_data(user, theme):
    return {
        'full_name': user[COL_FULL_NAME],
        'username': user[COL_USERNAME],
        'bio': user[COL_BIO],
        'joined': user[COL_CREATED_AT],
        'theme': theme,
    }


def _extract_create_form(form):
    username = form.get('username', '').strip()
    full_name = form.get('full_name', '').strip()
    bio = form.get('bio', '').strip()
    return username, full_name, bio


# --------------------------------------------------------------------------- #
# Middleware and routes
# --------------------------------------------------------------------------- #

@app.middleware('response')
async def add_security_headers(request, response):
    response.headers.update(SECURITY_HEADERS)
    return response


@app.route('/')
async def index(request):
    return html(INDEX_PAGE)


@app.route('/profile')
async def view_profile(request):
    username = request.args.get('username', '')
    if not username:
        return html(MSG_USERNAME_REQUIRED)
    user = await get_user(username)
    if not user:
        return html(MSG_USER_NOT_FOUND)
    theme = _resolve_theme(request)
    safe_user_data = _build_safe_user_data(user, theme)
    return html(render_profile_page(user, safe_user_data))


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    if request.method == 'POST':
        form = await request.form
        username, full_name, bio = _extract_create_form(form)
        if not username or not full_name:
            return html(MSG_CREATE_FIELDS_REQUIRED)
        user_id = await create_user(username, full_name, bio)
        return html(render_profile_created(username))
    return html(CREATE_FORM_PAGE)


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
