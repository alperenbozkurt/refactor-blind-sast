"""Minimal Pyramid application with cookie-based authentication.

The module is organised into named constants, an immutable configuration
object and small private helper functions, while preserving the original
public interface (module-level names, view callables, signatures, routes
and command-line behaviour).
"""

import html  # noqa: F401  (kept for backwards compatibility)
import os
from dataclasses import dataclass

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response  # noqa: F401  (kept for backwards compatibility)
from pyramid.view import view_config

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DEFAULT_USERS = {
    'admin': 'password123',
    'user1': 'mypassword',
}

INVALID_CREDENTIALS_MESSAGE = "Invalid credentials for user '{username}'"

AUTH_SECRET = 's3cr3t'
AUTH_HASH_ALGORITHM = 'sha512'

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
<head><title>Login</title></head>
<body>
    <h1>Login</h1>
    % if error:
        <div style="color: red">${error}</div>
    % endif
    <form method="post">
        Username: <input type="text" name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>'''

DASHBOARD_TEMPLATE = '''<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
    <h1>Welcome ${username}</h1>
    <a href="${request.route_url('logout')}">Logout</a>
</body>
</html>'''

DEFAULT_TEMPLATES = {
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

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543


# ---------------------------------------------------------------------------
# Configuration object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Immutable container for application-level configuration."""

    auth_secret: str = AUTH_SECRET
    auth_hash_algorithm: str = AUTH_HASH_ALGORITHM
    templates_dir: str = TEMPLATES_DIR
    host: str = SERVER_HOST
    port: int = SERVER_PORT


APP_CONFIG = AppConfig()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class UserDB:

    def __init__(self):
        self.users = dict(DEFAULT_USERS)

    def validate_user(self, username, password):
        return self.users.get(username) == password


db = UserDB()


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
        if db.validate_user(username, password):
            headers = remember(request, username)
            return HTTPFound(location=request.route_url('dashboard'), headers=headers)
        return {'error': INVALID_CREDENTIALS_MESSAGE.format(username=username)}
    return {}


@view_config(route_name='dashboard', renderer='templates/dashboard.pt')
def dashboard_view(request):
    if not authenticated_userid(request):
        return HTTPFound(location=request.route_url('login'))
    return {'username': authenticated_userid(request)}


@view_config(route_name='logout')
def logout_view(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


# ---------------------------------------------------------------------------
# Application setup helpers
# ---------------------------------------------------------------------------

def _configure_security(config, app_config: AppConfig) -> None:
    from pyramid.authentication import AuthTktAuthenticationPolicy
    from pyramid.authorization import ACLAuthorizationPolicy
    authn_policy = AuthTktAuthenticationPolicy(
        app_config.auth_secret, hashalg=app_config.auth_hash_algorithm
    )
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)


def _write_template(templates_dir: str, filename: str, content: str) -> None:
    with open(os.path.join(templates_dir, filename), 'w') as f:
        f.write(content)


def _ensure_templates(templates_dir: str, templates) -> None:
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    for filename, content in templates.items():
        _write_template(templates_dir, filename, content)


def _add_routes(config, routes) -> None:
    for name, pattern in routes:
        config.add_route(name, pattern)


# ---------------------------------------------------------------------------
# WSGI application factory
# ---------------------------------------------------------------------------

def main(global_config, **settings):
    config = Configurator(settings=settings)
    _configure_security(config, APP_CONFIG)
    _ensure_templates(APP_CONFIG.templates_dir, DEFAULT_TEMPLATES)
    _add_routes(config, ROUTES)
    config.scan()
    return config.make_wsgi_app()


# ---------------------------------------------------------------------------
# Security helpers (thin wrappers kept for backwards compatibility)
# ---------------------------------------------------------------------------

def remember(request, username):
    from pyramid.security import remember
    return remember(request, username)


def forget(request):
    from pyramid.security import forget
    return forget(request)


def authenticated_userid(request):
    from pyramid.security import authenticated_userid
    return authenticated_userid(request)


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    app = main({})
    server = make_server(APP_CONFIG.host, APP_CONFIG.port, app)
    server.serve_forever()
