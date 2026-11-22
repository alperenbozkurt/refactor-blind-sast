from sanic import Sanic, response
from sanic.response import html
from datetime import datetime
import uuid
import json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_NAME = 'Issue'
HOST = '0.0.0.0'
PORT = 8000

LOGIN_PATH = '/login'
DASHBOARD_PATH = '/dashboard'

DEFAULT_BIO = 'No bio provided'
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'
INVALID_CREDENTIALS_STATUS = 401

# NOTE: Templates deliberately interpolate user-supplied values verbatim
# (the "HTML" customisation fields), preserving the original behaviour.
INDEX_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>User Dashboard</title>
        </head>
        <body>
            <h1>Welcome</h1>
            <a href="/login">Login</a> | <a href="/register">Register</a>
        </body>
        </html>
    """

LOGIN_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Login</title>
            </head>
            <body>
                <h1>Login</h1>
                <form method="POST">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <button type="submit">Login</button>
                </form>
            </body>
            </html>
        """

DASHBOARD_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{user_name}'s Dashboard</title>
            <style>
                .dashboard {{ padding: 20px; }}
                .user-section {{ border: 1px solid #ccc; padding: 15px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                {custom_welcome}
                <div class="user-section">
                    <h3>About Me</h3>
                    <div class="bio">{custom_bio}</div>
                </div>
                <div class="preferences-form">
                    <h3>Customize Dashboard</h3>
                    <form action="/save_preferences" method="POST">
                        <input type="hidden" name="token" value="{token}">
                        <label>Custom Welcome Message (HTML):</label>
                        <textarea name="custom_welcome">{welcome_input}</textarea>
                        <label>Custom Bio (HTML):</label>
                        <textarea name="custom_bio">{bio_input}</textarea>
                        <button type="submit">Save Preferences</button>
                    </form>
                </div>
            </div>
        </body>
        </html>
        """

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------
app = Sanic(APP_NAME)

users = {
    'admin': {
        'password': 'admin123',
        'name': 'Administrator',
        'role': 'admin',
        'bio': 'System administrator account',
        'last_login': None,
    }
}
sessions = {}
user_preferences = {}


class UserSession:

    def __init__(self, username):
        self.token = str(uuid.uuid4())
        self.username = username
        self.created_at = datetime.now()
        sessions[self.token] = self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _credentials_valid(username, password):
    return username in users and users[username]['password'] == password


def _dashboard_redirect(token):
    return response.redirect(f'{DASHBOARD_PATH}?token={token}')


def _login_redirect():
    return response.redirect(LOGIN_PATH)


def render_user_dashboard(user_data, preferences, token):
    custom_welcome = preferences.get(
        'custom_welcome', f"<h2>Welcome, {user_data['name']}!</h2>"
    )
    custom_bio = preferences.get('custom_bio', user_data.get('bio', DEFAULT_BIO))
    return DASHBOARD_TEMPLATE.format(
        user_name=user_data['name'],
        custom_welcome=custom_welcome,
        custom_bio=custom_bio,
        token=token,
        welcome_input=preferences.get('custom_welcome', ''),
        bio_input=preferences.get('custom_bio', ''),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/', methods=['GET'])
async def index(request):
    return html(INDEX_TEMPLATE)


@app.route('/login', methods=['GET', 'POST'])
async def login(request):
    if request.method == 'GET':
        return html(LOGIN_TEMPLATE)
    form_data = request.form
    username = form_data.get('username')
    password = form_data.get('password')
    if _credentials_valid(username, password):
        session = UserSession(username)
        users[username]['last_login'] = datetime.now().isoformat()
        return _dashboard_redirect(session.token)
    return html(INVALID_CREDENTIALS_MESSAGE, status=INVALID_CREDENTIALS_STATUS)


@app.route('/dashboard', methods=['GET'])
async def dashboard(request):
    token = request.args.get('token')
    if token not in sessions:
        return _login_redirect()
    session = sessions[token]
    user = users[session.username]
    preferences = user_preferences.get(session.username, {})
    return html(render_user_dashboard(user, preferences, token))


@app.route('/save_preferences', methods=['POST'])
async def save_preferences(request):
    token = request.form.get('token')
    if token not in sessions:
        return _login_redirect()
    session = sessions[token]
    user_preferences[session.username] = {
        'custom_welcome': request.form.get('custom_welcome'),
        'custom_bio': request.form.get('custom_bio'),
    }
    return _dashboard_redirect(token)


if __name__ == '__main__':
    app.run(host=HOST, port=PORT)
