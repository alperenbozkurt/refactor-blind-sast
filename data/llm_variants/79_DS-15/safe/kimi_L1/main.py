"""Minimal Pyramid application with cookie-based authentication.

Serves a home page, a login/logout flow, and a protected dashboard.
Page templates are (re)written to the templates directory on startup.
"""

import hashlib
import html
import os
import secrets
from wsgiref.simple_server import make_server

from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response  # noqa: F401 (kept for compatibility)
from pyramid.security import (
    authenticated_userid as pyramid_authenticated_userid,
    forget as pyramid_forget,
    remember as pyramid_remember,
)
from pyramid.view import view_config

# Password hashing parameters.
SALT_HEX_BYTES = 16
PBKDF2_HASH_NAME = 'sha256'
PBKDF2_ITERATIONS = 100000

# Authentication cookie settings.
AUTH_COOKIE_SECRET_BYTES = 64

TEMPLATES_DIR = 'templates'

HOME_TEMPLATE = '''<!DOCTYPE html>
<html>
<head><title>Home</title></head>
<body>
    <h1>Welcome</h1>
    <a href="${request.route_url('login')}">Login</a>
</body>
</html>'''

LOGIN_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <h1>Login</h1>
    % if error:
        <div style="color: red">${error | h}</div>  <!-- Fixed: Added h filter for escaping -->
    % endif
    <form method="post">
        <input type="hidden" name="csrf_token" value="${request.session.get_csrf_token()}">
        Username: <input type="text" name="username" required><br>
        Password: <input type="password" name="password" required><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>'''

DASHBOARD_TEMPLATE = '''<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
    <h1>Welcome ${username | h}</h1>  <!-- Added h filter for escaping -->
    <form action="${request.route_url('logout')}" method="post">
        <input type="hidden" name="csrf_token" value="${request.session.get_csrf_token()}">
        <button type="submit">Logout</button>
    </form>
</body>
</html>'''

TEMPLATES = {
    'home.pt': HOME_TEMPLATE,
    'login.pt': LOGIN_TEMPLATE,
    'dashboard.pt': DASHBOARD_TEMPLATE,
}


class UserDB:
    """In-memory user database storing salted PBKDF2 password hashes."""

    def __init__(self):
        self.users = {
            'admin': self._hash_password('password123'),
            'user1': self._hash_password('mypassword'),
        }

    def _hash_password(self, password):
        salt = secrets.token_hex(SALT_HEX_BYTES)
        return f"{salt}:{self._pbkdf2_hex(password, salt)}"

    def validate_user(self, username, password):
        stored = self.users.get(username)
        if not stored:
            return False
        salt, hashed = stored.split(':')
        return hashed == self._pbkdf2_hex(password, salt)

    @staticmethod
    def _pbkdf2_hex(password, salt):
        """Return the hex PBKDF2-HMAC digest of ``password`` with ``salt``."""
        return hashlib.pbkdf2_hmac(
            PBKDF2_HASH_NAME,
            password.encode(),
            salt.encode(),
            PBKDF2_ITERATIONS,
        ).hex()


db = UserDB()


@view_config(route_name='home', renderer='templates/home.pt')
def home_view(request):
    return {}


@view_config(route_name='login', renderer='templates/login.pt')
def login_view(request):
    if request.method != 'POST':
        return {}

    username = request.params.get('username', '')
    password = request.params.get('password', '')
    if not username or not password:
        return {'error': 'Username and password are required'}

    if db.validate_user(username, password):
        headers = remember(request, username)
        return HTTPFound(location=request.route_url('dashboard'), headers=headers)

    error_msg = f"Invalid credentials for user '{html.escape(username)}'"
    return {'error': error_msg}


@view_config(route_name='dashboard', renderer='templates/dashboard.pt')
def dashboard_view(request):
    username = authenticated_userid(request)
    if not username:
        return HTTPFound(location=request.route_url('login'))
    return {'username': html.escape(username)}


@view_config(route_name='logout')
def logout_view(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


def _configure_security(config):
    """Set authentication, authorization, and CSRF policies on ``config``."""
    authn_policy = AuthTktAuthenticationPolicy(
        secrets.token_urlsafe(AUTH_COOKIE_SECRET_BYTES),
        hashalg='sha512',
        secure=True,
        httponly=True,
        samesite='Lax',
    )
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    config.set_default_csrf_options(require_csrf=True)


def _write_templates(directory):
    """Create ``directory`` if needed and (re)write all page templates."""
    if not os.path.exists(directory):
        os.makedirs(directory)
    for filename, content in TEMPLATES.items():
        with open(os.path.join(directory, filename), 'w') as f:
            f.write(content)


def _add_routes(config):
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('dashboard', '/dashboard')
    config.add_route('logout', '/logout')


def main(global_config, **settings):
    config = Configurator(settings=settings)
    _configure_security(config)
    _write_templates(TEMPLATES_DIR)
    _add_routes(config)
    config.scan()
    return config.make_wsgi_app()


def remember(request, username):
    return pyramid_remember(request, username)


def forget(request):
    return pyramid_forget(request)


def authenticated_userid(request):
    return pyramid_authenticated_userid(request)


if __name__ == '__main__':
    app = main({})
    server = make_server('0.0.0.0', 6543, app)
    server.serve_forever()
