from sanic import Sanic
from sanic.response import html
from sanic.exceptions import NotFound
import aiosqlite
import uuid
from datetime import datetime
import html as html_escape
import json
import secrets

DB_PATH = 'profiles.db'
VALID_THEMES = ['light', 'dark']
DEFAULT_THEME = 'light'

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'",
}

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        full_name TEXT,
        bio TEXT,
        created_at TEXT
    )
"""

INDEX_HTML = """
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
    """

CREATE_FORM_HTML = """
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
    """

app = Sanic('ProfileApp')
app.config.SECRET = secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


@app.listener('before_server_start')
async def setup_db(app, loop):
    await init_db()


async def create_user(username, full_name, bio):
    sanitized_username = html_escape.escape(username)
    sanitized_full_name = html_escape.escape(full_name)
    sanitized_bio = html_escape.escape(bio)
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO users VALUES (?, ?, ?, ?, ?)',
            (user_id, sanitized_username, sanitized_full_name, sanitized_bio, created_at),
        )
        await db.commit()
    return user_id


async def get_user(username):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM users WHERE username = ?', (username,))
        return await cursor.fetchone()


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_profile_page(user, theme):
    """Render the profile page for a user row (id, username, full_name, bio, created_at)."""
    _, username, full_name, bio, joined = user[:5]
    safe_user_data = {
        'full_name': full_name,
        'username': username,
        'bio': bio,
        'joined': joined,
        'theme': theme,
    }
    escape = html_escape.escape
    # NOTE: the page markup (including the inline script) is intentionally
    # kept byte-for-byte identical to the original behaviour.
    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{escape(username)}'s Profile</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}
                .dark {{ background: #333; color: white; }}
            </style>
        </head>
        <body id="body">
            <div class="profile">
                <h1>{escape(full_name)}</h1>
                <p>@{escape(username)}</p>
                <div id="bio">{escape(bio)}</div>
                <p><small>Joined: {escape(joined)}</small></p>
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


def get_theme(request):
    theme = request.args.get('theme', DEFAULT_THEME)
    return theme if theme in VALID_THEMES else DEFAULT_THEME


# ---------------------------------------------------------------------------
# Middleware and routes
# ---------------------------------------------------------------------------

@app.middleware('response')
async def add_security_headers(request, response):
    response.headers.update(SECURITY_HEADERS)
    return response


@app.route('/')
async def index(request):
    return html(INDEX_HTML)


@app.route('/profile')
async def view_profile(request):
    username = request.args.get('username', '')
    if not username:
        return html('Username parameter is required')

    user = await get_user(username)
    if not user:
        return html('User not found')

    return html(render_profile_page(user, get_theme(request)))


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    if request.method == 'POST':
        form = await request.form
        username = form.get('username', '').strip()
        full_name = form.get('full_name', '').strip()
        bio = form.get('bio', '').strip()

        if not username or not full_name:
            return html('Username and full name are required')

        await create_user(username, full_name, bio)
        return html(
            f"Profile created! <a href='/profile?username={html_escape.escape(username)}'>View profile</a>"
        )

    return html(CREATE_FORM_HTML)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
