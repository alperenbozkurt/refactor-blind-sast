"""Minimal Pyramid authentication demo, refactored for maintainability.

The behaviour is identical to the original module; the code is simply
organised around named constants, small helper functions and a
configuration object so it scales better in a larger codebase.
"""

import hashlib
import html
import os
import secrets
from dataclasses import dataclass

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response
from pyramid.view import view_config

# ---------------------------------------------------------------------------
# Password hashing constants
# ---------------------------------------------------------------------------

PBKDF2_HASH_NAME = 'sha256'
PBKDF2_ITERATIONS = 100_000
SALT_HEX_BYTES = 16
PASSWORD_SEPARATOR = ':'

DEFAULT_USERS = {
    'admin': 'password123',
    'user1': 'mypassword',
}

# ---------------------------------------------------------------------------
# Authentication policy configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthPolicySettings:
    """Settings for the AuthTkt authentication policy."""

    secret_urlsafe_bytes: int = 64
    hashalg: str = 'sha512'
    secure: bool = True
    httponly: bool = True
    samesite: str = 'Lax'


AUTH_POLICY_SETTINGS = AuthPolicySettings()

# ---------------------------------------------------------------------------
# Template constants
# ---------------------------------------------------------------------------

TEMPLATE_DIR = 'templates'

HOME_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head><title>Home</title></head>\n'
    '<body>\n'
    '    <h1>Welcome</h1>\n'
    '    <a href="${request.route_url(\'login\')}">Login</a>\n'
    '</body>\n'
    '</html>'
)

LOGIN_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head>\n'
    '    <title>Login</title>\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '</head>\n'
    '<body>\n'
    '    <h1>Login</h1>\n'
    '    % if error:\n'
    '        <div style="color: red">${error | h}</div>  <!-- Fixed: Added h filter for escaping -->\n'
    '    % endif\n'
    '    <form method="post">\n'
    '        <input type="hidden" name="csrf_token" value="${request.session.get_csrf_token()}">\n'
    '        Username: <input type="text" name="username" required><br>\n'
    '        Password: <input type="password" name="password" required><br>\n'
    '        <input type="submit" value="Login">\n'
    '    </form>\n'
    '</body>\n'
    '</html>'
)

DASHBOARD_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head><title>Dashboard</title></head>\n'
    '<body>\n'
    '    <h1>Welcome ${username | h}</h1>  <!-- Added h filter for escaping -->\n'
    '    <form action="${request.route_url(\'logout\')}" method="post">\n'
    '        <input type="hidden" name="csrf_token" value="${request.session.get_csrf_token()}">\n'
    '        <button type="submit">Logout</button>\n'
    '    </form>\n'
    '</body>\n'
    '</html>'
)

TEMPLATES = {
    'home.pt': HOME_TEMPLATE,
    'login.pt': LOGIN_TEMPLATE,
    'dashboard.pt': DASHBOARD_TEMPLATE,
}

# ---------------------------------------------------------------------------
# Route table and other constants
# ---------------------------------------------------------------------------

ROUTES = (
    ('home', '/'),
    ('login', '/login'),
    ('dashboard', '/dashboard'),
    ('logout', '/logout'),
)

ERROR_REQUIRED_FIELDS = 'Username and password are required'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543


# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------


class UserDB:
    """In-memory user store with salted PBKDF2 password hashing."""

    def __init__(self):
        self.users = {
            username: self._hash_password(password)
            for username, password in DEFAULT_USERS.items()
        }

    @staticmethod
    def _derive_hash(password, salt):
        return hashlib.pbkdf2_hmac(
            PBKDF2_HASH_NAME,
            password.encode(),
            salt.encode(),
            PBKDF2_ITERATIONS,
        ).hex()

    def _hash_password(self, password):
        salt = secrets.token_hex(SALT_HEX_BYTES)
        return f"{salt}{PASSWORD_SEPARATOR}{self._derive_hash(password, salt)}"

    def validate_user(self, username, password):
        stored = self.users.get(username)
        if not stored:
            return False
        (salt, hashed) = stored.split(PASSWORD_SEPARATOR)
        new_hash = self._derive_hash(password, salt)
        return hashed == new_hash


db = UserDB()


# ---------------------------------------------------------------------------
# Thin wrappers around pyramid.security (kept lazy-imported on purpose)
# ---------------------------------------------------------------------------


def remember(request, username):
    from pyramid.security import remember as _remember
    return _remember(request, username)


def forget(request):
    from pyramid.security import forget as _forget
    return _forget(request)


def authenticated_userid(request):
    from pyramid.security import authenticated_userid as _authenticated_userid
    return _authenticated_userid(request)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@view_config(route_name='home', renderer='templates/home.pt')
def home_view(request):
    return {}


@view_config(route_name='login', renderer='templates/login.pt')
def login_view(request):
    if request.method == 'POST':
        username = request.params.get('username', '')
        password = request.params.get('password', '')
        if not username or not password:
            return {'error': ERROR_REQUIRED_FIELDS}
        if db.validate_user(username, password):
            headers = remember(request, username)
            return HTTPFound(location=request.route_url('dashboard'), headers=headers)
        error_msg = f"Invalid credentials for user '{html.escape(username)}'"
        return {'error': error_msg}
    return {}


@view_config(route_name='dashboard', renderer='templates/dashboard.pt')
def dashboard_view(request):
    userid = authenticated_userid(request)
    if not userid:
        return HTTPFound(location=request.route_url('login'))
    return {'username': html.escape(userid)}


@view_config(route_name='logout')
def logout_view(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


# ---------------------------------------------------------------------------
# Application factory helpers
# ---------------------------------------------------------------------------


def _write_templates(template_dir, templates):
    """Ensure the template directory exists and write every template file."""
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    for filename, content in templates.items():
        with open(os.path.join(template_dir, filename), 'w') as f:
            f.write(content)


def _configure_security(config, policy_settings):
    """Install authentication/authorization policies and CSRF defaults."""
    from pyramid.authentication import AuthTktAuthenticationPolicy
    from pyramid.authorization import ACLAuthorizationPolicy
    authn_policy = AuthTktAuthenticationPolicy(
        secrets.token_urlsafe(policy_settings.secret_urlsafe_bytes),
        hashalg=policy_settings.hashalg,
        secure=policy_settings.secure,
        httponly=policy_settings.httponly,
        samesite=policy_settings.samesite,
    )
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    config.set_default_csrf_options(require_csrf=True)


def _register_routes(config, routes):
    for route_name, pattern in routes:
        config.add_route(route_name, pattern)


def main(global_config, **settings):
    config = Configurator(settings=settings)
    _configure_security(config, AUTH_POLICY_SETTINGS)
    _write_templates(TEMPLATE_DIR, TEMPLATES)
    _register_routes(config, ROUTES)
    config.scan()
    return config.make_wsgi_app()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    app = main({})
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()
