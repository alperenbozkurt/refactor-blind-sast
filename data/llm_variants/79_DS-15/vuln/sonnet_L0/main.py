from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
import os
import html


class UserDB:

    def __init__(self):
        self.users = {'admin': 'password123', 'user1': 'mypassword'}

    def validate_user(self, username, password):
        return self.users.get(username) == password


db = UserDB()


def _page(title, body_lines):
    lines = ['<!DOCTYPE html>',
             '<html>',
             '<head><title>%s</title></head>' % title,
             '<body>']
    lines.extend(body_lines)
    lines.extend(['</body>', '</html>'])
    return '\n'.join(lines)


TEMPLATES_DIR = 'templates'

TEMPLATES = {
    'home.pt': _page('Home', [
        '    <h1>Welcome</h1>',
        '    <a href="${request.route_url(\'login\')}">Login</a>',
    ]),
    'login.pt': _page('Login', [
        '    <h1>Login</h1>',
        '    % if error:',
        '        <div style="color: red">${error}</div>',
        '    % endif',
        '    <form method="post">',
        '        Username: <input type="text" name="username"><br>',
        '        Password: <input type="password" name="password"><br>',
        '        <input type="submit" value="Login">',
        '    </form>',
    ]),
    'dashboard.pt': _page('Dashboard', [
        '    <h1>Welcome ${username}</h1>',
        '    <a href="${request.route_url(\'logout\')}">Logout</a>',
    ]),
}

ROUTES = (
    ('home', '/'),
    ('login', '/login'),
    ('dashboard', '/dashboard'),
    ('logout', '/logout'),
)


def _write_templates():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    for name, content in TEMPLATES.items():
        with open(TEMPLATES_DIR + '/' + name, 'w') as f:
            f.write(content)


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
        return {'error': f"Invalid credentials for user '{username}'"}
    return {}


@view_config(route_name='dashboard', renderer='templates/dashboard.pt')
def dashboard_view(request):
    userid = authenticated_userid(request)
    if not userid:
        return HTTPFound(location=request.route_url('login'))
    return {'username': userid}


@view_config(route_name='logout')
def logout_view(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


def main(global_config, **settings):
    config = Configurator(settings=settings)
    from pyramid.authentication import AuthTktAuthenticationPolicy
    from pyramid.authorization import ACLAuthorizationPolicy
    config.set_authentication_policy(
        AuthTktAuthenticationPolicy('s3cr3t', hashalg='sha512'))
    config.set_authorization_policy(ACLAuthorizationPolicy())
    _write_templates()
    for name, pattern in ROUTES:
        config.add_route(name, pattern)
    config.scan()
    return config.make_wsgi_app()


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
    server = make_server('0.0.0.0', 6543, app)
    server.serve_forever()
