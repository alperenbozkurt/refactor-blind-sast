from sanic import Sanic, response
from sanic.response import html
from datetime import datetime
import uuid
import json
import bleach

app = Sanic('SecureDashboard')

ALLOWED_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'b', 'i', 'strong', 'em', 'p', 'br']
ALLOWED_ATTRIBUTES = {}

_ROOT_PATH = '/'
_LOGIN_PATH = '/login'
_DASHBOARD_PATH = '/dashboard'
_SAVE_PREFERENCES_PATH = '/save_preferences'

_DEFAULT_BIO = 'No bio provided'
_DEFAULT_WELCOME_TEMPLATE = '<h2>Welcome, {name}!</h2>'
_INVALID_CREDENTIALS_BODY = 'Invalid credentials'
_UNAUTHORIZED_STATUS = 401

_SERVER_HOST = '0.0.0.0'
_SERVER_PORT = 8000
_SERVER_DEBUG = False

_INDEX_PAGE = '''
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

_LOGIN_PAGE = '''
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

users = {'admin': {'password': 'admin123', 'name': 'Administrator', 'role': 'admin', 'bio': 'System administrator account', 'last_login': None}}
sessions = {}
user_preferences = {}


def sanitize_html(content):
    return bleach.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)


def _clean_user_field(content):
    return bleach.clean(content)


def _credentials_are_valid(username, password):
    return username in users and users[username]['password'] == password


def _build_safe_user_data(user):
    return {
        'name': _clean_user_field(user['name']),
        'bio': _clean_user_field(user.get('bio', _DEFAULT_BIO)),
    }


def _build_safe_preferences(preferences, safe_user_data):
    return {
        'custom_welcome': sanitize_html(
            preferences.get(
                'custom_welcome',
                _DEFAULT_WELCOME_TEMPLATE.format(name=safe_user_data['name']),
            )
        ),
        'custom_bio': sanitize_html(preferences.get('custom_bio', safe_user_data['bio'])),
    }


def _dashboard_url(token):
    return f'{_DASHBOARD_PATH}?token={token}'


def _redirect_to_login():
    return response.redirect(_LOGIN_PATH)


def _redirect_to_dashboard(token):
    return response.redirect(_dashboard_url(token))


class UserSession:

    def __init__(self, username):
        self.token = str(uuid.uuid4())
        self.username = username
        self.created_at = datetime.now()
        sessions[self.token] = self


@app.route(_ROOT_PATH, methods=['GET'])
async def index(request):
    return html(_INDEX_PAGE)


@app.route(_LOGIN_PATH, methods=['GET', 'POST'])
async def login(request):
    if request.method == 'GET':
        return html(_LOGIN_PAGE)
    form_data = request.form
    username = form_data.get('username')
    password = form_data.get('password')
    if _credentials_are_valid(username, password):
        session = UserSession(username)
        users[username]['last_login'] = datetime.now().isoformat()
        return _redirect_to_dashboard(session.token)
    return html(_INVALID_CREDENTIALS_BODY, status=_UNAUTHORIZED_STATUS)


@app.route(_DASHBOARD_PATH, methods=['GET'])
async def dashboard(request):
    token = request.args.get('token')
    if token not in sessions:
        return _redirect_to_login()
    session = sessions[token]
    user = users[session.username]
    preferences = user_preferences.get(session.username, {})
    safe_user_data = _build_safe_user_data(user)
    safe_preferences = _build_safe_preferences(preferences, safe_user_data)
    return await render_template(user_data=safe_user_data, preferences=safe_preferences, token=token)


async def render_template(user_data, preferences, token):
    return html(f'''
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
                {preferences['custom_welcome']}
                <div class="user-section">
                    <h3>About Me</h3>
                    <div class="bio">{preferences['custom_bio']}</div>
                </div>
                <div class="preferences-form">
                    <h3>Customize Dashboard</h3>
                    <form action="/save_preferences" method="POST">
                        <input type="hidden" name="token" value="{token}">
                        <label>Custom Welcome Message (HTML):</label>
                        <textarea name="custom_welcome">{preferences.get('custom_welcome', '')}</textarea>
                        <label>Custom Bio (HTML):</label>
                        <textarea name="custom_bio">{preferences.get('custom_bio', '')}</textarea>
                        <button type="submit">Save Preferences</button>
                    </form>
                </div>
            </div>
        </body>
        </html>
    ''')


@app.route(_SAVE_PREFERENCES_PATH, methods=['POST'])
async def save_preferences(request):
    token = request.form.get('token')
    if token not in sessions:
        return _redirect_to_login()
    session = sessions[token]
    user_preferences[session.username] = {
        'custom_welcome': sanitize_html(request.form.get('custom_welcome', '')),
        'custom_bio': sanitize_html(request.form.get('custom_bio', '')),
    }
    return _redirect_to_dashboard(token)


if __name__ == '__main__':
    app.run(host=_SERVER_HOST, port=_SERVER_PORT, debug=_SERVER_DEBUG)
