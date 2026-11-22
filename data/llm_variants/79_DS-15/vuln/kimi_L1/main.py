"""Minimal Pyramid application demonstrating cookie-based authentication."""

import html
import os

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

HOME_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head><title>Home</title></head>\n'
    '<body>\n'
    '    <h1>Welcome</h1>\n'
    "    <a href=\"${request.route_url('login')}\">Login</a>\n"
    '</body>\n'
    '</html>'
)

LOGIN_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head><title>Login</title></head>\n'
    '<body>\n'
    '    <h1>Login</h1>\n'
    '    % if error:\n'
    '        <div style="color: red">${error}</div>\n'
    '    % endif\n'
    '    <form method="post">\n'
    '        Username: <input type="text" name="username"><br>\n'
    '        Password: <input type="password" name="password"><br>\n'
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
    '    <h1>Welcome ${username}</h1>\n'
    "    <a href=\"${request.route_url('logout')}\">Logout</a>\n"
    '</body>\n'
    '</html>'
)

DEFAULT_TEMPLATES = {
    'home.pt': HOME_TEMPLATE,
    'login.pt': LOGIN_TEMPLATE,
    'dashboard.pt': DASHBOARD_TEMPLATE,
}


class UserDB:
    """In-memory user store used for credential validation."""

    def __init__(self):
        self.users = {'admin': 'password123', 'user1': 'mypassword'}

    def validate_user(self, username, password):
        return self.users.get(username) == password


db = UserDB()


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
            return HTTPFound(location=request.route_url('dashboard'),
                             headers=headers)
        error_msg = f"Invalid credentials for user '{username}'"
        return {'error': error_msg}
    return {}


@view_config(route_name='dashboard', renderer='templates/dashboard.pt')
def dashboard_view(request):
    username = authenticated_userid(request)
    if not username:
        return HTTPFound(location=request.route_url('login'))
    return {'username': username}


@view_config(route_name='logout')
def logout_view(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


def remember(request, username):
    return _remember(request, username)


def forget(request):
    return _forget(request)


def authenticated_userid(request):
    return _authenticated_userid(request)


def _configure_security(config):
    from pyramid.authentication import AuthTktAuthenticationPolicy
    from pyramid.authorization import ACLAuthorizationPolicy
    authn_policy = AuthTktAuthenticationPolicy('s3cr3t', hashalg='sha512')
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)


def _write_default_templates():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    for filename, content in DEFAULT_TEMPLATES.items():
        path = os.path.join(TEMPLATES_DIR, filename)
        with open(path, 'w') as f:
            f.write(content)


def _add_routes(config):
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('dashboard', '/dashboard')
    config.add_route('logout', '/logout')


def main(global_config, **settings):
    config = Configurator(settings=settings)
    _configure_security(config)
    _write_default_templates()
    _add_routes(config)
    config.scan()
    return config.make_wsgi_app()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    app = main({})
    server = make_server('0.0.0.0', 6543, app)
    server.serve_forever()
