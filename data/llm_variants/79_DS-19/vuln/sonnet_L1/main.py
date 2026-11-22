from sanic import Sanic
from sanic.response import html
from sanic.exceptions import NotFound
import aiosqlite
import uuid
from datetime import datetime

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

INDEX_PAGE = '''
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
    '''

CREATE_PROFILE_FORM_PAGE = '''
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
    '''

app = Sanic('ProfileApp')


def render_profile_page(user, theme):
    """Render the profile page for a user row and the requested theme."""
    return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{user[1]}'s Profile</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .profile {{ border: 1px solid #ddd; padding: 20px; margin-top: 20px; }}
                .dark {{ background: #333; color: white; }}
            </style>
        </head>
        <body id="body">
            <div class="profile">
                <h1>{user[2]}</h1>
                <p>@{user[1]}</p>
                <div id="bio">{user[3]}</div>
                <p><small>Joined: {user[4]}</small></p>
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
    '''


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
        await db.execute(
            INSERT_USER_SQL,
            (user_id, username, full_name, bio, created_at),
        )
        await db.commit()
    return user_id


async def get_user(username):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(SELECT_USER_SQL, (username,))
        return await cursor.fetchone()


@app.route('/')
async def index(request):
    return html(INDEX_PAGE)


@app.route('/profile')
async def view_profile(request):
    username = request.args.get('username', '')
    if not username:
        return html('Username parameter is required')

    user = await get_user(username)
    if not user:
        return html('User not found')

    theme = request.args.get('theme', 'light')
    return html(render_profile_page(user, theme))


@app.route('/create', methods=['GET', 'POST'])
async def create_profile(request):
    if request.method == 'POST':
        form = await request.form
        user_id = await create_user(
            form.get('username'), form.get('full_name'), form.get('bio')
        )
        return html(
            f"Profile created! <a href='/profile?username={form.get('username')}'>View profile</a>"
        )
    return html(CREATE_PROFILE_FORM_PAGE)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
