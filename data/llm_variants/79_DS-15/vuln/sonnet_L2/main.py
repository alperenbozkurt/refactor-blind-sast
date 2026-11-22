from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
import os
import html

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Route names and patterns
ROUTE_HOME = 'home'
ROUTE_LOGIN = 'login'
ROUTE_DASHBOARD = 'dashboard'
ROUTE_LOGOUT = 'logout'

ROUTES = (
    (ROUTE_HOME, '/'),
    (ROUTE_LOGIN, '/login'),
    (ROUTE_DASHBOARD, '/dashboard'),
    (ROUTE_LOGOUT, '/logout'),
)

# Templates
TEMPLATES_DIR = 'templates'
HOME_TEMPLATE = 'templates/home.pt'
LOGIN_TEMPLATE = 'templates/login.pt'
DASHBOARD_TEMPLATE = 'templates/dashboard.pt'

HOME_TEMPLATE_CONTENT = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head><title>Home</title></head>\n'
    '<body>\n'
    '    <h1>Welcome</h1>\n'
    '    <a href="${request.route_url(\'login\')}">Login</a>\n'
    '</body>\n'
    '</html>'
)

LOGIN_TEMPLATE_CONTENT = (
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

DASHBOARD_TEMPLATE_CONTENT = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head><title>Dashboard</title></head>\n'
    '<body>\n'
    '    <h1>Welcome ${username}</h1>\n'
    '    <a href="${request.route_url(\'logout\')}">Logout</a>\n'
    '</body>\n'
    '</html>'
)

TEMPLATE_FILES = (
    (HOME_TEMPLATE, HOME_TEMPLATE_CONTENT),
    (LOGIN_TEMPLATE, LOGIN_TEMPLATE_CONTENT),
    (DASHBOARD_TEMPLATE, DASHBOARD_TEMPLATE_CONTENT),
)

# Authentication
AUTH_SECRET = 's3cr3t'
AUTH_HASH_ALGORITHM = 'sha512'

# Request handling
HTTP_POST = 'POST'
PARAM_USERNAME = 'username'
PARAM_PASSWORD = 'password'

# Development server
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543


# --------------------------------------------------------------------------- #
# Data layer
# --------------------------------------------------------------------------- #

class UserDB:

    def __init__(self):
        self.users = {'admin': 'password123', 'user1': 'mypassword'}

    def validate_user(self, username, password):
        return self.users.get(username) == password


db = UserDB()


# --------------------------------------------------------------------------- #
# View helpers
# --------------------------------------------------------------------------- #

def _redirect_to(request, route_name, headers=None):
    """Build a redirect response to the given route."""
    location = request.route_url(route_name)
    if headers is None:
        return HTTPFound(location=location)
    return HTTPFound(location=location, headers=headers)


def _invalid_credentials_message(username):
    return f"Invalid credentials for user '{username}'"


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #

@view_config(route_name=ROUTE_HOME, renderer=HOME_TEMPLATE)
def home_view(request):
    return {}


@view_config(route_name=ROUTE_LOGIN, renderer=LOGIN_TEMPLATE)
def login_view(request):
    if request.method == HTTP_POST:
        username = request.params.get(PARAM_USERNAME, '')
        password = request.params.get(PARAM_PASSWORD, '')
        if db.validate_user(username, password):
            headers = remember(request, username)
            return _redirect_to(request, ROUTE_DASHBOARD, headers=headers)
        return {'error': _invalid_credentials_message(username)}
    return {}


@view_config(route_name=ROUTE_DASHBOARD, renderer=DASHBOARD_TEMPLATE)
def dashboard_view(request):
    userid = authenticated_userid(request)
    if not userid:
        return _redirect_to(request, ROUTE_LOGIN)
    return {'username': userid}


@view_config(route_name=ROUTE_LOGOUT)
def logout_view(request):
    headers = forget(request)
    return _redirect_to(request, ROUTE_HOME, headers=headers)


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

def _configure_security(config):
    from pyramid.authentication import AuthTktAuthenticationPolicy
    from pyramid.authorization import ACLAuthorizationPolicy
    authn_policy = AuthTktAuthenticationPolicy(AUTH_SECRET,
                                               hashalg=AUTH_HASH_ALGORITHM)
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)


def _write_templates():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    for path, content in TEMPLATE_FILES:
        with open(path, 'w') as f:
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


# --------------------------------------------------------------------------- #
# Security wrappers (imports deferred; names intentionally shadow pyramid's)
# --------------------------------------------------------------------------- #

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
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()
