from sanic import Sanic
from sanic.response import html
from sanic.exceptions import NotFound
import aiosqlite
import uuid
from datetime import datetime
import html as html_escape
import json
import secrets

APP_NAME = 'ProfileApp'
DATABASE_PATH = 'profiles.db'

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

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'",
}

DEFAULT_THEME = 'light'
VALID_THEMES = ('light', 'dark')

USERNAME_REQUIRED_MESSAGE = 'Username parameter is required'
USER_NOT_FOUND_MESSAGE = 'User not found'
REQUIRED_PROFILE_FIELDS_MESSAGE = 'Username and full name are required'

INDEX_HTML = (
    '\n'
    '        <!DOCTYPE html>\n'
    '        <html>\n'
    '        <head>\n'
    '            <title>Profile System</title>\n'
    '            <meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '            <style>\n'
    '                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n'
    '                .profile { border: 1px solid #ddd; padding: 20px; margin-top: 20px; }\n'
    '            </style>\n'
    '        </head>\n'
    '        <body>\n'
    '            <h1>Profile System</h1>\n'
    '            <form action="/profile" method="GET">\n'
    '                <input type="text" name="username" placeholder="Enter username" required>\n'
    '                <button type="submit">View Profile</button>\n'
    '            </form>\n'
    '            <p>Try usernames: alice, bob, charlie</p>\n'
    '        </body>\n'
    '        </html>\n'
    '    '
)

CREATE_PROFILE_HTML = (
    '\n'
    '        <h1>Create Profile</h1>\n'
    '        <form method="POST">\n'
    '            <p>\n'
    '                <label>Username:</label><br>\n'
    '                <input type="text" name="username" required maxlength="50">\n'
    '            </p>\n'
    '            <p>\n'
    '                <label>Full Name:</label><br>\n'
    '                <input type="text" name="full_name" required maxlength="100">\n'
    '            </p>\n'
    '            <p>\n'
    '                <label>Bio:</label><br>\n'
    '                <textarea name="bio" rows="4" maxlength="500"></textarea>\n'
    '            </p>\n'
    '            <button type="submit">Create Profile</button>\n'
    '        </form>\n'
    '    '
)

app = Sanic(APP_NAME)
app.config.SECRET = secrets.token_urlsafe(32)


def db_connection():
    return aiosqlite.connect(DATABASE_PATH)


def escape_html(value):
    return html_escape.escape(value)


def resolve_theme(request):
    theme = request.args.get('theme', DEFAULT_THEME)
    if theme not in VALID_THEMES:
        theme = DEFAULT_THEME
    return theme


def build_safe_user_data(user, theme):
    return {
        'full_name': user[2],
        'username': user[1],
        'bio': user[3],
        'joined': user[4],
        'theme': theme,
    }


def render_profile_page(user, safe_user_data):
    return f"""\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>{escape_html(user[1])}'s Profile</title>\n            <meta name="viewport" content="width=device-width, initial-scale=1">\n            <style>\n                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}\n                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}\n                .dark {{ background: #333; color: white; }}\n            </style>\n        </head>\n        <body id="body">\n            <div class="profile">\n                <h1>{escape_html(user[2])}</h1>\n                <p>@{escape_html(user[1])}</p>\n                <div id="bio">{escape_html(user[3])}</div>\n                <p><small>Joined: {escape_html(user[4])}</small></p>\n            </div>\n            <a href="/">Back to home</a>\n            \n            <script>\n                // Safely apply theme\n                const userData = {json.dumps(safe_user_data)};\n                document.getElementById("body").className = userData.theme;\n                \n                // Safe way to handle URL parameters\n                const urlParams = new URLSearchParams(window.location.search);\n                const welcomeMessage = urlParams.get('welcome') || 'Welcome to my profile!';\n                \n                // Safely add content to DOM\n                const bioElement = document.getElementById("bio");\n                const welcomePara = document.createElement('p');\n                welcomePara.innerHTML = '<em>' + document.createTextNode(welcomeMessage).textContent + '</em>';\n                bioElement.appendChild(welcomePara);\n            </script>\n        </body>\n        </html>\n    """


def render_profile_created(username):
    return f"Profile created! <a href='/profile?username={escape_html(username)}'>View profile</a>"


async def init_db():
    async with db_connection() as db:
        await db.execute(CREATE_USERS_TABLE_SQL)
        await db.commit()


@app.listener('before_server_start')
async def setup_db(app, loop):
    await init_db()


async def create_user(username, full_name, bio):
    sanitized_username = escape_html(username)
    sanitized_full_name = escape_html(full_name)
    sanitized_bio = escape_html(bio)
    user_id = str(uuid.uuid4())
    async with db_connection() as db:
        await db.execute(INSERT_USER_SQL, (user_id, sanitized_username, sanitized_full_name, sanitized_bio, datetime.now().isoformat()))
        await db.commit()
    return user_id


async def get_user(username):
    async with db_connection() as db:
        cursor = await db.execute(SELECT_USER_BY_USERNAME_SQL, (username,))
        return await cursor.fetchone()


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
        return html(USERNAME_REQUIRED_MESSAGE)
    user = await get_user(username)
    if not user:
        return html(USER_NOT_FOUND_MESSAGE)
    theme = resolve_theme(request)
    safe_user_data = build_safe_user_data(user, theme)
    return html(render_profile_page(user, safe_user_data))


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    if request.method == 'POST':
        form = await request.form
        username = form.get('username', '').strip()
        full_name = form.get('full_name', '').strip()
        bio = form.get('bio', '').strip()
        if not username or not full_name:
            return html(REQUIRED_PROFILE_FIELDS_MESSAGE)
        user_id = await create_user(username, full_name, bio)
        return html(render_profile_created(username))
    return html(CREATE_PROFILE_HTML)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
