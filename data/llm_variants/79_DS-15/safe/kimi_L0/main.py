"""A small Pyramid application with login, dashboard and logout views."""

import hashlib
import html
import os
import secrets

from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response
from pyramid.security import (
    authenticated_userid as _authenticated_userid,
    forget as _forget,
    remember as _remember,
)
from pyramid.view import view_config

TEMPLATES_DIR = 'templates'

HOME_TEMPLATE = """<!DOCTYPE html>
<html>
<head><title>Home</title></head>
<body>
    <h1>Welcome</h1>
    <a href="${request.route_url('login')}">Login</a>
</body>
</html>"""

LOGIN_TEMPLATE = """<!DOCTYPE html>
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
</html>"""

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
    <h1>Welcome ${username | h}</h1>  <!-- Added h filter for escaping -->
    <form action="${request.route_url('logout')}" method="post">
        <input type="hidden" name="csrf_token" value="${request.session.get_csrf_token()}">
        <button type="submit">Logout</button>
    </form>
</body>
</html>"""

TEMPLATES = {
    'home.pt': HOME_TEMPLATE,
    'login.pt': LOGIN_TEMPLATE,
    'dashboard.pt': DASHBOARD_TEMPLATE,
}

ROUTES = (
    ('home', '/'),
    ('login', '/login'),
    ('dashboard', '/dashboard'),
    ('logout', '/logout'),
)

_HASH_ALGORITHM = 'sha256'
_PBKDF2_ITERATIONS = 100000


def remember(request, username):
    return _remember(request, username)


def forget(request):
    return _forget(request)


def authenticated_userid(request):
    return _authenticated_userid(request)


def _hash_with_salt(password, salt):
    return hashlib.pbkdf2_hmac(
        _HASH_ALGORITHM,
        password.encode(),
        salt.encode(),
        _PBKDF2_ITERATIONS,
    ).hex()


class UserDB:

    def __init__(self):
        self.users = {
            'admin': self._hash_password('password123'),
            'user1': self._hash_password('mypassword'),
        }

    def _hash_password(self, password):
        salt = secrets.token_hex(16)
        return f"{salt}:{_hash_with_salt(password, salt)}"

    def validate_user(self, username, password):
        stored = self.users.get(username)
        if not stored:
            return False
        salt, hashed = stored.split(':')
        return hashed == _hash_with_salt(password, salt)


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
    userid = authenticated_userid(request)
    if not userid:
        return HTTPFound(location=request.route_url('login'))
    return {'username': html.escape(userid)}


@view_config(route_name='logout')
def logout_view(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


def _configure_security(config):
    authn_policy = AuthTktAuthenticationPolicy(
        secrets.token_urlsafe(64),
        hashalg='sha512',
        secure=True,
        httponly=True,
        samesite='Lax',
    )
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    config.set_default_csrf_options(require_csrf=True)


def _write_templates():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    for filename, content in TEMPLATES.items():
        with open(os.path.join(TEMPLATES_DIR, filename), 'w') as f:
            f.write(content)


def _add_routes(config):
    for name, pattern in ROUTES:
        config.add_route(name, pattern)


def main(global_config, **settings):
    config = Configurator(settings=settings)
    _configure_security(config)
    _write_templates()
    _add_routes(config)
    config.scan()
    return config.make_wsgi_app()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    app = main({})
    server = make_server('0.0.0.0', 6543, app)
    server.serve_forever()
