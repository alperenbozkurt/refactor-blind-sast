import html as html_escape
import json
import secrets
import uuid
from datetime import datetime

import aiosqlite
from sanic import Sanic
from sanic.exceptions import NotFound
from sanic.response import html

DATABASE_PATH = 'profiles.db'

CREATE_TABLE_SQL = 'CREATE TABLE IF NOT EXISTS users\n                          (id TEXT PRIMARY KEY,\n                          username TEXT UNIQUE,\n                          full_name TEXT,\n                          bio TEXT,\n                          created_at TEXT)'
INSERT_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
SELECT_USER_SQL = 'SELECT * FROM users WHERE username = ?'

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'",
}

DEFAULT_THEME = 'light'
VALID_THEMES = ('light', 'dark')

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

CREATE_PROFILE_PAGE = '''
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

app = Sanic('ProfileApp')
app.config.SECRET = secrets.token_urlsafe(32)


async def init_db():
    """Create the users table if it does not already exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


@app.listener('before_server_start')
async def setup_db(app, loop):
    """Initialize the database before the server starts."""
    await init_db()


async def create_user(username, full_name, bio):
    """Insert a new user with HTML-escaped fields and return the user ID."""
    sanitized_username = html_escape.escape(username)
    sanitized_full_name = html_escape.escape(full_name)
    sanitized_bio = html_escape.escape(bio)
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            INSERT_USER_SQL,
            (user_id, sanitized_username, sanitized_full_name, sanitized_bio, created_at),
        )
        await db.commit()
    return user_id


async def get_user(username):
    """Return the user row for the given username, or None if not found."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(SELECT_USER_SQL, (username,))
        return await cursor.fetchone()


@app.middleware('response')
async def add_security_headers(request, response):
    """Attach security-related headers to every response."""
    response.headers.update(SECURITY_HEADERS)
    return response


@app.route('/')
async def index(request):
    """Render the home page with the profile lookup form."""
    return html(INDEX_PAGE)


@app.route('/profile')
async def view_profile(request):
    """Render the profile page for the requested username."""
    username = request.args.get('username', '')
    if not username:
        return html('Username parameter is required')

    user = await get_user(username)
    if not user:
        return html('User not found')

    theme = request.args.get('theme', DEFAULT_THEME)
    if theme not in VALID_THEMES:
        theme = DEFAULT_THEME

    _, user_username, user_full_name, user_bio, user_joined = user[:5]
    escaped_username = html_escape.escape(user_username)
    escaped_full_name = html_escape.escape(user_full_name)
    escaped_bio = html_escape.escape(user_bio)
    escaped_joined = html_escape.escape(user_joined)

    safe_user_data = {
        'full_name': user_full_name,
        'username': user_username,
        'bio': user_bio,
        'joined': user_joined,
        'theme': theme,
    }
    user_data_json = json.dumps(safe_user_data)

    return html(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{escaped_username}'s Profile</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}
                .dark {{ background: #333; color: white; }}
            </style>
        </head>
        <body id="body">
            <div class="profile">
                <h1>{escaped_full_name}</h1>
                <p>@{escaped_username}</p>
                <div id="bio">{escaped_bio}</div>
                <p><small>Joined: {escaped_joined}</small></p>
            </div>
            <a href="/">Back to home</a>
            
            <script>
                // Safely apply theme
                const userData = {user_data_json};
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
    """)


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    """Render the creation form on GET and store a new profile on POST."""
    if request.method == 'POST':
        form = await request.form
        username = form.get('username', '').strip()
        full_name = form.get('full_name', '').strip()
        bio = form.get('bio', '').strip()
        if not username or not full_name:
            return html('Username and full name are required')
        user_id = await create_user(username, full_name, bio)
        return html(
            f"Profile created! <a href='/profile?username={html_escape.escape(username)}'>View profile</a>"
        )
    return html(CREATE_PROFILE_PAGE)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
