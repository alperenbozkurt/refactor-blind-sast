from sanic import Sanic, response
from sanic.response import html
from datetime import datetime
from dataclasses import dataclass
import uuid
import json
import bleach


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

APP_NAME = 'SecureDashboard'

ALLOWED_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'b', 'i', 'strong', 'em', 'p', 'br']
ALLOWED_ATTRIBUTES = {}

ROUTE_INDEX = '/'
ROUTE_LOGIN = '/login'
ROUTE_REGISTER = '/register'
ROUTE_DASHBOARD = '/dashboard'
ROUTE_SAVE_PREFERENCES = '/save_preferences'

DEFAULT_BIO = 'No bio provided'
STATUS_UNAUTHORIZED = 401
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'


@dataclass(frozen=True)
class ServerConfig:
    """Network/runtime settings used when launching the server."""
    host: str = '0.0.0.0'
    port: int = 8000
    debug: bool = False


SERVER_CONFIG = ServerConfig()


# --------------------------------------------------------------------------- #
# Application state (in-memory stores)
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# HTML templates
# --------------------------------------------------------------------------- #

INDEX_TEMPLATE = (
    '\n'
    '        <!DOCTYPE html>\n'
    '        <html>\n'
    '        <head>\n'
    '            <title>User Dashboard</title>\n'
    '        </head>\n'
    '        <body>\n'
    '            <h1>Welcome</h1>\n'
    '            <a href="/login">Login</a> | <a href="/register">Register</a>\n'
    '        </body>\n'
    '        </html>\n'
    '    '
)

LOGIN_TEMPLATE = (
    '\n'
    '            <!DOCTYPE html>\n'
    '            <html>\n'
    '            <head>\n'
    '                <title>Login</title>\n'
    '            </head>\n'
    '            <body>\n'
    '                <h1>Login</h1>\n'
    '                <form method="POST">\n'
    '                    <input type="text" name="username" placeholder="Username" required>\n'
    '                    <input type="password" name="password" placeholder="Password" required>\n'
    '                    <button type="submit">Login</button>\n'
    '                </form>\n'
    '            </body>\n'
    '            </html>\n'
    '        '
)

# Rendered with str.format(); literal braces are therefore doubled.
DASHBOARD_TEMPLATE = (
    '\n'
    '        <!DOCTYPE html>\n'
    '        <html>\n'
    '        <head>\n'
    "            <title>{name}'s Dashboard</title>\n"
    '            <style>\n'
    '                .dashboard {{ padding: 20px; }}\n'
    '                .user-section {{ border: 1px solid #ccc; padding: 15px; margin-bottom: 20px; }}\n'
    '            </style>\n'
    '        </head>\n'
    '        <body>\n'
    '            <div class="dashboard">\n'
    '                {welcome}\n'
    '                <div class="user-section">\n'
    '                    <h3>About Me</h3>\n'
    '                    <div class="bio">{bio}</div>\n'
    '                </div>\n'
    '                <div class="preferences-form">\n'
    '                    <h3>Customize Dashboard</h3>\n'
    '                    <form action="/save_preferences" method="POST">\n'
    '                        <input type="hidden" name="token" value="{token}">\n'
    '                        <label>Custom Welcome Message (HTML):</label>\n'
    '                        <textarea name="custom_welcome">{welcome_value}</textarea>\n'
    '                        <label>Custom Bio (HTML):</label>\n'
    '                        <textarea name="custom_bio">{bio_value}</textarea>\n'
    '                        <button type="submit">Save Preferences</button>\n'
    '                    </form>\n'
    '                </div>\n'
    '            </div>\n'
    '        </body>\n'
    '        </html>\n'
    '    '
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def sanitize_html(content):
    return bleach.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)


def _dashboard_url(token):
    return f'{ROUTE_DASHBOARD}?token={token}'


def _redirect_to_login():
    return response.redirect(ROUTE_LOGIN)


def _redirect_to_dashboard(token):
    return response.redirect(_dashboard_url(token))


def _find_session(token):
    """Return the session for ``token`` or ``None`` if it does not exist."""
    if token not in sessions:
        return None
    return sessions[token]


def _credentials_valid(username, password):
    return username in users and users[username]['password'] == password


def _build_safe_user_data(user):
    return {
        'name': bleach.clean(user['name']),
        'bio': bleach.clean(user.get('bio', DEFAULT_BIO)),
    }


def _build_safe_preferences(preferences, safe_user_data):
    default_welcome = f"<h2>Welcome, {safe_user_data['name']}!</h2>"
    return {
        'custom_welcome': sanitize_html(preferences.get('custom_welcome', default_welcome)),
        'custom_bio': sanitize_html(preferences.get('custom_bio', safe_user_data['bio'])),
    }


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

class UserSession:

    def __init__(self, username):
        self.token = str(uuid.uuid4())
        self.username = username
        self.created_at = datetime.now()
        sessions[self.token] = self


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route(ROUTE_INDEX, methods=['GET'])
async def index(request):
    return html(INDEX_TEMPLATE)


@app.route(ROUTE_LOGIN, methods=['GET', 'POST'])
async def login(request):
    if request.method == 'GET':
        return html(LOGIN_TEMPLATE)
    form_data = request.form
    username = form_data.get('username')
    password = form_data.get('password')
    if _credentials_valid(username, password):
        session = UserSession(username)
        users[username]['last_login'] = datetime.now().isoformat()
        return _redirect_to_dashboard(session.token)
    return html(INVALID_CREDENTIALS_MESSAGE, status=STATUS_UNAUTHORIZED)


@app.route(ROUTE_DASHBOARD, methods=['GET'])
async def dashboard(request):
    token = request.args.get('token')
    session = _find_session(token)
    if session is None:
        return _redirect_to_login()
    user = users[session.username]
    preferences = user_preferences.get(session.username, {})
    safe_user_data = _build_safe_user_data(user)
    safe_preferences = _build_safe_preferences(preferences, safe_user_data)
    return await render_template(user_data=safe_user_data, preferences=safe_preferences, token=token)


async def render_template(user_data, preferences, token):
    return html(DASHBOARD_TEMPLATE.format(
        name=user_data['name'],
        welcome=preferences['custom_welcome'],
        bio=preferences['custom_bio'],
        token=token,
        welcome_value=preferences.get('custom_welcome', ''),
        bio_value=preferences.get('custom_bio', ''),
    ))


@app.route(ROUTE_SAVE_PREFERENCES, methods=['POST'])
async def save_preferences(request):
    token = request.form.get('token')
    session = _find_session(token)
    if session is None:
        return _redirect_to_login()
    user_preferences[session.username] = {
        'custom_welcome': sanitize_html(request.form.get('custom_welcome', '')),
        'custom_bio': sanitize_html(request.form.get('custom_bio', '')),
    }
    return _redirect_to_dashboard(token)


if __name__ == '__main__':
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port, debug=SERVER_CONFIG.debug)
