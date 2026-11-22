import tornado.ioloop
import tornado.web
import tornado.template
import os
import json
import uuid
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEMPLATES_DIR = 'templates'
LOGIN_TEMPLATE_NAME = 'login.html'
MAIN_TEMPLATE_NAME = 'main.html'
USER_COOKIE_NAME = 'user'
COOKIE_SECRET = '__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__'
LOGIN_URL = '/login'
HTTP_FORBIDDEN = 403
SERVER_PORT = 8888
SERVER_URL_MESSAGE = 'Server started at http://localhost:8888'

LOGIN_TEMPLATE_CONTENT = '\n'.join([
    '<!DOCTYPE html>',
    '<html>',
    '<head><title>Login</title></head>',
    '<body>',
    '    <form method="post">',
    '        <input type="text" name="username" placeholder="Username">',
    '        <button type="submit">Login</button>',
    '    </form>',
    '</body>',
    '</html>',
])

MAIN_TEMPLATE_CONTENT = '\n'.join([
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>Notification System</title>',
    '    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>',
    '</head>',
    '<body>',
    '    <h1>Welcome, {{ user }}</h1>',
    '    ',
    '    <div>',
    '        <h2>Send Notification</h2>',
    '        <textarea id="message" placeholder="Notification message"></textarea>',
    '        <button onclick="sendNotification()">Send</button>',
    '    </div>',
    '    ',
    '    <div id="notifications"></div>',
    '    ',
    '    <script>',
    '        function sendNotification() {',
    "            const message = $('#message').val();",
    "            $.post('/notify', {message: message}, function(data) {",
    '                loadNotifications();',
    '            });',
    '        }',
    '        ',
    '        function loadNotifications() {',
    "            $.get('/get_notifications', function(data) {",
    '                const notes = JSON.parse(data);',
    "                let html = '<h2>Your Notifications</h2><ul>';",
    '                notes.forEach(note => {',
    '',
    '                    html += `<li>${note.message} <small>${note.timestamp}</small></li>`;',
    '                });',
    "                html += '</ul>';",
    "                $('#notifications').html(html);",
    '            });',
    '        }',
    '        ',
    '        // Load notifications on page load',
    '        $(document).ready(loadNotifications);',
    '    </script>',
    '</body>',
    '</html>',
])

TEMPLATE_FILES = (
    (LOGIN_TEMPLATE_NAME, LOGIN_TEMPLATE_CONTENT),
    (MAIN_TEMPLATE_NAME, MAIN_TEMPLATE_CONTENT),
)


# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------
def _current_timestamp():
    return datetime.now().isoformat()


def _new_note_id():
    return str(uuid.uuid4())


class NotificationSystem:

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        if user_id not in self.notifications:
            self.notifications[user_id] = []
        note_id = _new_note_id()
        self.notifications[user_id].append({
            'id': note_id,
            'message': message,
            'timestamp': _current_timestamp(),
        })
        return note_id

    def get_notifications(self, user_id):
        return self.notifications.get(user_id, [])


notification_system = NotificationSystem()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie(USER_COOKIE_NAME)

    def _current_username(self):
        return self.current_user.decode()

    def _reject_unauthenticated(self):
        """Set a 403 status if no user is logged in; return True if rejected."""
        if not self.current_user:
            self.set_status(HTTP_FORBIDDEN)
            return True
        return False


class MainHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.redirect(LOGIN_URL)
            return
        self.render(MAIN_TEMPLATE_NAME, user=self._current_username())


class LoginHandler(BaseHandler):

    def get(self):
        self.render(LOGIN_TEMPLATE_NAME)

    def post(self):
        username = self.get_body_argument('username')
        self.set_secure_cookie(USER_COOKIE_NAME, username)
        self.redirect('/')


class NotificationHandler(BaseHandler):

    def post(self):
        if self._reject_unauthenticated():
            return
        user_id = self._current_username()
        message = self.get_body_argument('message')
        note_id = notification_system.add_notification(user_id, message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):

    def get(self):
        if self._reject_unauthenticated():
            return
        user_id = self._current_username()
        notes = notification_system.get_notifications(user_id)
        self.write(json.dumps(notes))


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
def _ensure_templates_dir():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)


def _write_template(name, content):
    with open(TEMPLATES_DIR + '/' + name, 'w') as f:
        f.write(content)


def _write_templates():
    _ensure_templates_dir()
    for name, content in TEMPLATE_FILES:
        _write_template(name, content)


def _build_routes():
    return [
        ('/', MainHandler),
        ('/login', LoginHandler),
        ('/notify', NotificationHandler),
        ('/get_notifications', GetNotificationsHandler),
    ]


def make_app():
    _write_templates()
    return tornado.web.Application(_build_routes(), cookie_secret=COOKIE_SECRET)


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    print(SERVER_URL_MESSAGE)
    tornado.ioloop.IOLoop.current().start()
