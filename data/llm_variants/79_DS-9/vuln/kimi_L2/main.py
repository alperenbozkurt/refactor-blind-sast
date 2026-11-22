"""Sanic user dashboard application with session-based authentication."""

import json
import uuid
from datetime import datetime

from sanic import Sanic, response
from sanic.response import html

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_NAME = 'Issue'


class ServerConfig:
    """Settings for the built-in development server."""

    host = '0.0.0.0'
    port = 8000


SERVER_CONFIG = ServerConfig()

# Routes and URL building.
LOGIN_ROUTE = '/login'
DASHBOARD_URL_TEMPLATE = '/dashboard?token={token}'

# Form / query-string field names.
USERNAME_FIELD = 'username'
PASSWORD_FIELD = 'password'
TOKEN_FIELD = 'token'
CUSTOM_WELCOME_FIELD = 'custom_welcome'
CUSTOM_BIO_FIELD = 'custom_bio'

# User-facing defaults and messages.
DEFAULT_BIO = 'No bio provided'
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'
HTTP_UNAUTHORIZED = 401

# ---------------------------------------------------------------------------
# Page templates (leading/trailing whitespace is significant)
# ---------------------------------------------------------------------------

INDEX_PAGE = '''
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
    '''

LOGIN_PAGE = '''
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
        '''

# ---------------------------------------------------------------------------
# Application and in-memory state
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
    """A server-side login session, registered in the global session store."""

    def __init__(self, username):
        self.token = str(uuid.uuid4())
        self.username = username
        self.created_at = datetime.now()
        sessions[self.token] = self


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def authenticate_user(username, password):
    """Return True when the supplied credentials match a registered user."""
    return username in users and users[username]['password'] == password


def get_session(token):
    """Return the session for ``token``, or None when it does not exist."""
    return sessions.get(token)


def get_preferences(username):
    """Return the stored dashboard preferences for ``username``."""
    return user_preferences.get(username, {})


def dashboard_url(token):
    """Build the dashboard URL for the given session token."""
    return DASHBOARD_URL_TEMPLATE.format(token=token)


def render_user_dashboard(user_data, preferences, token):
    """Render the dashboard HTML page for a user."""
    custom_welcome = preferences.get(
        CUSTOM_WELCOME_FIELD, f"<h2>Welcome, {user_data['name']}!</h2>"
    )
    custom_bio = preferences.get(
        CUSTOM_BIO_FIELD, user_data.get('bio', DEFAULT_BIO)
    )
    return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{user_data['name']}'s Dashboard</title>
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
                        <textarea name="custom_welcome">{preferences.get(CUSTOM_WELCOME_FIELD, '')}</textarea>
                        <label>Custom Bio (HTML):</label>
                        <textarea name="custom_bio">{preferences.get(CUSTOM_BIO_FIELD, '')}</textarea>
                        <button type="submit">Save Preferences</button>
                    </form>
                </div>
            </div>
        </body>
        </html>
        '''


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@app.route('/', methods=['GET'])
async def index(request):
    return html(INDEX_PAGE)


@app.route('/login', methods=['GET', 'POST'])
async def login(request):
    if request.method == 'GET':
        return html(LOGIN_PAGE)
    form_data = request.form
    username = form_data.get(USERNAME_FIELD)
    password = form_data.get(PASSWORD_FIELD)
    if authenticate_user(username, password):
        session = UserSession(username)
        users[username]['last_login'] = datetime.now().isoformat()
        return response.redirect(dashboard_url(session.token))
    return html(INVALID_CREDENTIALS_MESSAGE, status=HTTP_UNAUTHORIZED)


@app.route('/dashboard', methods=['GET'])
async def dashboard(request):
    token = request.args.get(TOKEN_FIELD)
    session = get_session(token)
    if session is None:
        return response.redirect(LOGIN_ROUTE)
    user = users[session.username]
    preferences = get_preferences(session.username)
    return html(render_user_dashboard(user, preferences, token))


@app.route('/save_preferences', methods=['POST'])
async def save_preferences(request):
    token = request.form.get(TOKEN_FIELD)
    session = get_session(token)
    if session is None:
        return response.redirect(LOGIN_ROUTE)
    user_preferences[session.username] = {
        CUSTOM_WELCOME_FIELD: request.form.get(CUSTOM_WELCOME_FIELD),
        CUSTOM_BIO_FIELD: request.form.get(CUSTOM_BIO_FIELD),
    }
    return response.redirect(dashboard_url(token))


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    """Run the development server."""
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port)


if __name__ == '__main__':
    main()
