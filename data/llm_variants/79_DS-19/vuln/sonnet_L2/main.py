from dataclasses import dataclass

import aiosqlite
import uuid
from datetime import datetime

from sanic import Sanic
from sanic.response import html
from sanic.exceptions import NotFound


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DatabaseConfig:
    path: str = 'profiles.db'


@dataclass(frozen=True)
class ServerConfig:
    host: str = '0.0.0.0'
    port: int = 8000
    debug: bool = True


APP_NAME = 'ProfileApp'
DB_CONFIG = DatabaseConfig()
SERVER_CONFIG = ServerConfig()

DEFAULT_THEME = 'light'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                          (id TEXT PRIMARY KEY,\n'
    '                          username TEXT UNIQUE,\n'
    '                          full_name TEXT,\n'
    '                          bio TEXT,\n'
    '                          created_at TEXT)'
)
INSERT_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
SELECT_USER_BY_USERNAME_SQL = 'SELECT * FROM users WHERE username = ?'

# Column indexes of the ``users`` table rows.
COL_ID = 0
COL_USERNAME = 1
COL_FULL_NAME = 2
COL_BIO = 3
COL_CREATED_AT = 4

# ---------------------------------------------------------------------------
# Response messages
# ---------------------------------------------------------------------------

MSG_USERNAME_REQUIRED = 'Username parameter is required'
MSG_USER_NOT_FOUND = 'User not found'

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Profile System</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .profile { border: 1px solid #ddd; padding: 20px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>Profile System</h1>
            <form action="/profile" method="GET">
                <input type="text" name="username" placeholder="Enter username">
                <button type="submit">View Profile</button>
            </form>
            <p>Try usernames: alice, bob, charlie</p>
        </body>
        </html>
    """

# NOTE: uses str.format placeholders, hence the doubled braces for CSS/JS.
PROFILE_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{username}'s Profile</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}
                .dark {{ background: #333; color: white; }}
            </style>
        </head>
        <body id="body">
            <div class="profile">
                <h1>{full_name}</h1>
                <p>@{username}</p>
                <div id="bio">{bio}</div>
                <p><small>Joined: {created_at}</small></p>
            </div>
            <a href="/">Back to home</a>
            
            <script>

                document.getElementById("body").className = "{theme}";
                

                const searchParams = new URLSearchParams(window.location.search);
                const welcomeMessage = searchParams.get('welcome') || 'Welcome to my profile!';
                document.getElementById("bio").innerHTML += '<p><em>' + welcomeMessage + '</em></p>';
            </script>
        </body>
        </html>
    """

CREATE_FORM_TEMPLATE = """
        <h1>Create Profile</h1>
        <form method="POST">
            <p>
                <label>Username:</label><br>
                <input type="text" name="username" required>
            </p>
            <p>
                <label>Full Name:</label><br>
                <input type="text" name="full_name" required>
            </p>
            <p>
                <label>Bio:</label><br>
                <textarea name="bio" rows="4"></textarea>
            </p>
            <button type="submit">Create Profile</button>
        </form>
    """

PROFILE_CREATED_TEMPLATE = (
    "Profile created! <a href='/profile?username={username}'>View profile</a>"
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = Sanic(APP_NAME)


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def _connect():
    """Open a connection to the profiles database."""
    return aiosqlite.connect(DB_CONFIG.path)


def _generate_user_id():
    return str(uuid.uuid4())


def _timestamp_now():
    return datetime.now().isoformat()


async def init_db():
    async with _connect() as db:
        await db.execute(CREATE_USERS_TABLE_SQL)
        await db.commit()


@app.listener('before_server_start')
async def setup_db(app, loop):
    await init_db()


async def create_user(username, full_name, bio):
    user_id = _generate_user_id()
    async with _connect() as db:
        await db.execute(
            INSERT_USER_SQL,
            (user_id, username, full_name, bio, _timestamp_now()),
        )
        await db.commit()
    return user_id


async def get_user(username):
    async with _connect() as db:
        cursor = await db.execute(SELECT_USER_BY_USERNAME_SQL, (username,))
        return await cursor.fetchone()


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_index():
    return INDEX_TEMPLATE


def render_profile(user, theme):
    return PROFILE_TEMPLATE.format(
        username=user[COL_USERNAME],
        full_name=user[COL_FULL_NAME],
        bio=user[COL_BIO],
        created_at=user[COL_CREATED_AT],
        theme=theme,
    )


def render_create_form():
    return CREATE_FORM_TEMPLATE


def render_profile_created(username):
    return PROFILE_CREATED_TEMPLATE.format(username=username)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
async def index(request):
    return html(render_index())


@app.route('/profile')
async def view_profile(request):
    username = request.args.get('username', '')
    if not username:
        return html(MSG_USERNAME_REQUIRED)
    user = await get_user(username)
    if not user:
        return html(MSG_USER_NOT_FOUND)
    theme = request.args.get('theme', DEFAULT_THEME)
    return html(render_profile(user, theme))


async def _handle_create_submission(request):
    form = await request.form
    user_id = await create_user(
        form.get('username'), form.get('full_name'), form.get('bio')
    )
    return html(render_profile_created(form.get('username')))


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    if request.method == 'POST':
        return await _handle_create_submission(request)
    return html(render_create_form())


if __name__ == '__main__':
    app.run(
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )
