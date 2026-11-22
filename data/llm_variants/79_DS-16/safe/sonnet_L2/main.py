import tornado.ioloop
import tornado.web
import tornado.template
import os
import json
import uuid
from datetime import datetime
import html
import secrets


# ---------------------------------------------------------------------------
# Configuration / constants
# ---------------------------------------------------------------------------

SERVER_PORT = 8888
TEMPLATES_DIR = 'templates'
LOGIN_TEMPLATE_NAME = 'login.html'
MAIN_TEMPLATE_NAME = 'main.html'
COOKIE_SECRET_BYTES = 64
USER_COOKIE_NAME = 'user'

ROUTE_MAIN = '/'
ROUTE_LOGIN = '/login'
ROUTE_NOTIFY = '/notify'
ROUTE_GET_NOTIFICATIONS = '/get_notifications'

HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403

SECURITY_HEADERS = (
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('X-XSS-Protection', '1; mode=block'),
    ('Content-Security-Policy', "default-src 'self'"),
)

LOGIN_TEMPLATE_HTML = '\n'.join([
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>Login</title>',
    '    <meta name="viewport" content="width=device-width, initial-scale=1">',
    '</head>',
    '<body>',
    '    <form method="post">',
    '        <input type="text" name="username" placeholder="Username" required>',
    '        <button type="submit">Login</button>',
    '    </form>',
    '</body>',
    '</html>',
])

MAIN_TEMPLATE_HTML = '\n'.join([
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
    '        <textarea id="message" placeholder="Notification message" required></textarea>',
    '        <button onclick="sendNotification()">Send</button>',
    '    </div>',
    '    ',
    '    <div id="notifications"></div>',
    '    ',
    '    <script>',
    '        function escapeHtml(text) {',
    "            const div = document.createElement('div');",
    '            div.textContent = text;',
    '            return div.innerHTML;',
    '        }',
    '        ',
    '        function sendNotification() {',
    "            const message = $('#message').val();",
    '            if (!message) return;',
    '            ',
    "            $.post('/notify', {message: message}, function(data) {",
    "                $('#message').val('');",
    '                loadNotifications();',
    '            });',
    '        }',
    '        ',
    '        function loadNotifications() {',
    "            $.get('/get_notifications', function(data) {",
    '                try {',
    '                    const notes = JSON.parse(data);',
    "                    let html = '<h2>Your Notifications</h2><ul>';",
    '                    notes.forEach(note => {',
    '                        // Fixed: Use textContent or proper escaping',
    '                        html += `<li>${escapeHtml(note.message)} <small>${escapeHtml(note.timestamp)}</small></li>`;',
    '                    });',
    "                    html += '</ul>';",
    "                    $('#notifications').html(html);",
    '                } catch (e) {',
    "                    console.error('Error loading notifications:', e);",
    '                }',
    '            });',
    '        }',
    '        ',
    '        // Load notifications on page load',
    '        $(document).ready(loadNotifications);',
    '    </script>',
    '</body>',
    '</html>',
])


# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

class NotificationSystem:

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        if user_id not in self.notifications:
            self.notifications[user_id] = []
        note_id = str(uuid.uuid4())
        self.notifications[user_id].append(self._build_notification(note_id, message))
        return note_id

    def get_notifications(self, user_id):
        return self.notifications.get(user_id, [])

    @staticmethod
    def _build_notification(note_id, message):
        return {
            'id': note_id,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }


notification_system = NotificationSystem()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_public_note(note):
    """Return only the fields of a notification that may be exposed."""
    return {
        'id': note['id'],
        'message': note['message'],
        'timestamp': note['timestamp'],
    }


def _write_template_file(filename, content):
    path = TEMPLATES_DIR + '/' + filename
    with open(path, 'w') as f:
        f.write(content)


def _ensure_templates():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    _write_template_file(LOGIN_TEMPLATE_NAME, LOGIN_TEMPLATE_HTML)
    _write_template_file(MAIN_TEMPLATE_NAME, MAIN_TEMPLATE_HTML)


def _build_routes():
    return [
        (ROUTE_MAIN, MainHandler),
        (ROUTE_LOGIN, LoginHandler),
        (ROUTE_NOTIFY, NotificationHandler),
        (ROUTE_GET_NOTIFICATIONS, GetNotificationsHandler),
    ]


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------

class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie(USER_COOKIE_NAME)

    def set_default_headers(self):
        for name, value in SECURITY_HEADERS:
            self.set_header(name, value)

    def _current_user_id(self):
        return self.current_user.decode()


class MainHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.redirect(ROUTE_LOGIN)
            return
        self.render(MAIN_TEMPLATE_NAME, user=html.escape(self._current_user_id()))


class LoginHandler(BaseHandler):

    def get(self):
        self.render(LOGIN_TEMPLATE_NAME)

    def post(self):
        username = self.get_body_argument('username', '').strip()
        if not username:
            self.set_status(HTTP_BAD_REQUEST)
            return
        self.set_secure_cookie(USER_COOKIE_NAME, username, httponly=True, secure=True, samesite='Lax')
        self.redirect(ROUTE_MAIN)


class NotificationHandler(BaseHandler):

    def post(self):
        if not self.current_user:
            self.set_status(HTTP_FORBIDDEN)
            return
        user_id = self._current_user_id()
        message = self.get_body_argument('message', '')
        sanitized_message = html.escape(message)
        if not sanitized_message:
            self.set_status(HTTP_BAD_REQUEST)
            return
        note_id = notification_system.add_notification(user_id, sanitized_message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.set_status(HTTP_FORBIDDEN)
            return
        user_id = self._current_user_id()
        notes = notification_system.get_notifications(user_id)
        safe_notes = [_to_public_note(note) for note in notes]
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(safe_notes))


# ---------------------------------------------------------------------------
# Application factory / entry point
# ---------------------------------------------------------------------------

def make_app():
    _ensure_templates()
    cookie_secret = secrets.token_urlsafe(COOKIE_SECRET_BYTES)
    return tornado.web.Application(
        _build_routes(),
        cookie_secret=cookie_secret,
        xsrf_cookies=True,
    )


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    print('Server started at http://localhost:%d' % SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
