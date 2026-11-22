import html
import os

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

AUTH_SECRET = 's3cr3t'
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
</html>"""

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
    <h1>Welcome ${username}</h1>
    <a href="${request.route_url('logout')}">Logout</a>
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


class UserDB:

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
    if request.method != 'POST':
        return {}
    username = request.params.get('username', '')
    password = request.params.get('password', '')
    if db.validate_user(username, password):
        headers = remember(request, username)
        return HTTPFound(location=request.route_url('dashboard'), headers=headers)
    return {'error': f"Invalid credentials for user '{username}'"}


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


def _write_templates():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    for filename, content in TEMPLATES.items():
        with open(os.path.join(TEMPLATES_DIR, filename), 'w') as f:
            f.write(content)


def main(global_config, **settings):
    config = Configurator(settings=settings)
    authn_policy = AuthTktAuthenticationPolicy(AUTH_SECRET, hashalg='sha512')
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    _write_templates()
    for name, pattern in ROUTES:
        config.add_route(name, pattern)
    config.scan()
    return config.make_wsgi_app()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    app = main({})
    server = make_server('0.0.0.0', 6543, app)
    server.serve_forever()
