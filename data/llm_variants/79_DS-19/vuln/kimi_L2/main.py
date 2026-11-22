"""Profile System web application.

A small Sanic + SQLite application for creating and viewing user
profiles, structured for use within a larger production codebase:

* runtime configuration lives in a single immutable ``Settings`` object
* SQL statements, messages and HTML templates are named constants
* database access is handled by small reusable helpers
* HTML rendering is separated from the request handlers
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

import aiosqlite
from sanic import Sanic
from sanic.exceptions import NotFound  # noqa: F401  (kept as part of the module namespace)
from sanic.response import html


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the application."""

    app_name: str = 'ProfileApp'
    database_path: str = 'profiles.db'
    host: str = '0.0.0.0'
    port: int = 8000
    debug: bool = True


SETTINGS = Settings()


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


# ---------------------------------------------------------------------------
# Messages and request defaults
# ---------------------------------------------------------------------------

USERNAME_REQUIRED_MESSAGE = 'Username parameter is required'
USER_NOT_FOUND_MESSAGE = 'User not found'
DEFAULT_THEME = 'light'


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

INDEX_PAGE_HTML = """
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

CREATE_PROFILE_PAGE_HTML = """
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


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class User(NamedTuple):
    """A single row from the ``users`` table."""

    id: str
    username: str
    full_name: str
    bio: str
    created_at: str


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def _connect_db():
    """Return a new connection to the profiles database."""
    return aiosqlite.connect(SETTINGS.database_path)


async def _execute(sql, params=()):
    """Execute a write statement and commit it."""
    async with _connect_db() as db:
        await db.execute(sql, params)
        await db.commit()


async def _fetch_one(sql, params=()):
    """Execute a query and return the first row, or ``None``."""
    async with _connect_db() as db:
        cursor = await db.execute(sql, params)
        return await cursor.fetchone()


async def init_db():
    """Create the ``users`` table if it does not already exist."""
    await _execute(CREATE_USERS_TABLE_SQL)


async def create_user(username, full_name, bio):
    """Insert a new user and return its generated id."""
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    await _execute(INSERT_USER_SQL, (user_id, username, full_name, bio, created_at))
    return user_id


async def get_user(username):
    """Return the row for ``username``, or ``None`` if it does not exist."""
    return await _fetch_one(SELECT_USER_BY_USERNAME_SQL, (username,))


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_profile_page(user, theme):
    """Render the profile page for ``user`` using the given ``theme``."""
    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{user.username}'s Profile</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}
                .dark {{ background: #333; color: white; }}
            </style>
        </head>
        <body id="body">
            <div class="profile">
                <h1>{user.full_name}</h1>
                <p>@{user.username}</p>
                <div id="bio">{user.bio}</div>
                <p><small>Joined: {user.created_at}</small></p>
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


def _render_profile_created(username):
    """Render the confirmation shown after a profile is created."""
    return f"Profile created! <a href='/profile?username={username}'>View profile</a>"


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Sanic(SETTINGS.app_name)


@app.listener('before_server_start')
async def setup_db(app, loop):
    await init_db()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
async def index(request):
    return html(INDEX_PAGE_HTML)


@app.route('/profile')
async def view_profile(request):
    username = request.args.get('username', '')
    if not username:
        return html(USERNAME_REQUIRED_MESSAGE)
    row = await get_user(username)
    if not row:
        return html(USER_NOT_FOUND_MESSAGE)
    theme = request.args.get('theme', DEFAULT_THEME)
    return html(_render_profile_page(User(*row), theme))


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    if request.method == 'POST':
        form = await request.form
        user_id = await create_user(form.get('username'), form.get('full_name'), form.get('bio'))
        return html(_render_profile_created(form.get('username')))
    return html(CREATE_PROFILE_PAGE_HTML)


if __name__ == '__main__':
    app.run(host=SETTINGS.host, port=SETTINGS.port, debug=SETTINGS.debug)
