from datetime import datetime
import uuid

import aiosqlite
from sanic import Sanic
from sanic.exceptions import NotFound
from sanic.response import html

app = Sanic('ProfileApp')

DB_PATH = 'profiles.db'

CREATE_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                          (id TEXT PRIMARY KEY,\n'
    '                          username TEXT UNIQUE,\n'
    '                          full_name TEXT,\n'
    '                          bio TEXT,\n'
    '                          created_at TEXT)'
)
INSERT_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
SELECT_USER_SQL = 'SELECT * FROM users WHERE username = ?'

INDEX_HTML = (
    '\n        <!DOCTYPE html>\n        <html>\n        <head>\n'
    '            <title>Profile System</title>\n            <style>\n'
    '                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n'
    '                .profile { border: 1px solid #ddd; padding: 20px; margin-top: 20px; }\n'
    '            </style>\n        </head>\n        <body>\n'
    '            <h1>Profile System</h1>\n'
    '            <form action="/profile" method="GET">\n'
    '                <input type="text" name="username" placeholder="Enter username">\n'
    '                <button type="submit">View Profile</button>\n'
    '            </form>\n'
    '            <p>Try usernames: alice, bob, charlie</p>\n'
    '        </body>\n        </html>\n    '
)

PROFILE_TEMPLATE = (
    '\n        <!DOCTYPE html>\n        <html>\n        <head>\n'
    "            <title>{username}'s Profile</title>\n"
    '            <style>\n'
    '                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}\n'
    '                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}\n'
    '                .dark {{ background: #333; color: white; }}\n'
    '            </style>\n        </head>\n        <body id="body">\n'
    '            <div class="profile">\n'
    '                <h1>{full_name}</h1>\n'
    '                <p>@{username}</p>\n'
    '                <div id="bio">{bio}</div>\n'
    '                <p><small>Joined: {joined}</small></p>\n'
    '            </div>\n'
    '            <a href="/">Back to home</a>\n'
    '            \n'
    '            <script>\n\n'
    '                document.getElementById("body").className = "{theme}";\n'
    '                \n\n'
    '                const searchParams = new URLSearchParams(window.location.search);\n'
    "                const welcomeMessage = searchParams.get('welcome') || 'Welcome to my profile!';\n"
    '                document.getElementById("bio").innerHTML += \'<p><em>\' + welcomeMessage + \'</em></p>\';\n'
    '            </script>\n'
    '        </body>\n        </html>\n    '
)

CREATE_FORM_HTML = (
    '\n        <h1>Create Profile</h1>\n        <form method="POST">\n'
    '            <p>\n'
    '                <label>Username:</label><br>\n'
    '                <input type="text" name="username" required>\n'
    '            </p>\n'
    '            <p>\n'
    '                <label>Full Name:</label><br>\n'
    '                <input type="text" name="full_name" required>\n'
    '            </p>\n'
    '            <p>\n'
    '                <label>Bio:</label><br>\n'
    '                <textarea name="bio" rows="4"></textarea>\n'
    '            </p>\n'
    '            <button type="submit">Create Profile</button>\n'
    '        </form>\n    '
)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


@app.listener('before_server_start')
async def setup_db(app, loop):
    await init_db()


async def create_user(username, full_name, bio):
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(INSERT_USER_SQL, (user_id, username, full_name, bio, created_at))
        await db.commit()
    return user_id


async def get_user(username):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(SELECT_USER_SQL, (username,))
        return await cursor.fetchone()


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

    theme = request.args.get('theme', 'light')
    return html(PROFILE_TEMPLATE.format(
        username=user[1],
        full_name=user[2],
        bio=user[3],
        joined=user[4],
        theme=theme,
    ))


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    if request.method == 'POST':
        form = await request.form
        username = form.get('username')
        await create_user(username, form.get('full_name'), form.get('bio'))
        return html(
            f"Profile created! <a href='/profile?username={form.get('username')}'>View profile</a>"
        )
    return html(CREATE_FORM_HTML)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
