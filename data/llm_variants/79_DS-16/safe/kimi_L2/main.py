"""Notification web application built with Tornado.

The refactored module keeps the original public interface unchanged:

* ``NotificationSystem`` and the ``notification_system`` singleton
* the request handlers (``BaseHandler``, ``MainHandler``, ``LoginHandler``,
  ``NotificationHandler`` and ``GetNotificationsHandler``)
* the ``make_app`` application factory
* the command-line entry point (``python <module>.py``)
"""

import html
import json
import os
import secrets
import uuid
from datetime import datetime

import tornado.ioloop
import tornado.template  # noqa: F401 -- kept for module-namespace compatibility
import tornado.web

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8888

TEMPLATES_DIR = 'templates'
LOGIN_TEMPLATE_NAME = 'login.html'
MAIN_TEMPLATE_NAME = 'main.html'
LOGIN_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, LOGIN_TEMPLATE_NAME)
MAIN_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, MAIN_TEMPLATE_NAME)

PATH_MAIN = '/'
PATH_LOGIN = '/login'
PATH_NOTIFY = '/notify'
PATH_GET_NOTIFICATIONS = '/get_notifications'

USER_COOKIE_NAME = 'user'
COOKIE_SECRET_NBYTES = 64
COOKIE_OPTIONS = {
    'httponly': True,
    'secure': True,
    'samesite': 'Lax',
}

# Security headers applied to every response, in order.
SECURITY_HEADERS = (
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('X-XSS-Protection', '1; mode=block'),
    ('Content-Security-Policy', "default-src 'self'"),
)

CONTENT_TYPE_JSON = 'application/json'

# ---------------------------------------------------------------------------
# HTML templates (written verbatim to disk when the app is created)
# ---------------------------------------------------------------------------

LOGIN_TEMPLATE = '<!DOCTYPE html>\n<html>\n<head>\n    <title>Login</title>\n    <meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n    <form method="post">\n        <input type="text" name="username" placeholder="Username" required>\n        <button type="submit">Login</button>\n    </form>\n</body>\n</html>'

MAIN_TEMPLATE = '<!DOCTYPE html>\n<html>\n<head>\n    <title>Notification System</title>\n    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>\n</head>\n<body>\n    <h1>Welcome, {{ user }}</h1>\n    \n    <div>\n        <h2>Send Notification</h2>\n        <textarea id="message" placeholder="Notification message" required></textarea>\n        <button onclick="sendNotification()">Send</button>\n    </div>\n    \n    <div id="notifications"></div>\n    \n    <script>\n        function escapeHtml(text) {\n            const div = document.createElement(\'div\');\n            div.textContent = text;\n            return div.innerHTML;\n        }\n        \n        function sendNotification() {\n            const message = $(\'#message\').val();\n            if (!message) return;\n            \n            $.post(\'/notify\', {message: message}, function(data) {\n                $(\'#message\').val(\'\');\n                loadNotifications();\n            });\n        }\n        \n        function loadNotifications() {\n            $.get(\'/get_notifications\', function(data) {\n                try {\n                    const notes = JSON.parse(data);\n                    let html = \'<h2>Your Notifications</h2><ul>\';\n                    notes.forEach(note => {\n                        // Fixed: Use textContent or proper escaping\n                        html += `<li>${escapeHtml(note.message)} <small>${escapeHtml(note.timestamp)}</small></li>`;\n                    });\n                    html += \'</ul>\';\n                    $(\'#notifications\').html(html);\n                } catch (e) {\n                    console.error(\'Error loading notifications:\', e);\n                }\n            });\n        }\n        \n        // Load notifications on page load\n        $(document).ready(loadNotifications);\n    </script>\n</body>\n</html>'


# ---------------------------------------------------------------------------
# Notification storage
# ---------------------------------------------------------------------------

class NotificationSystem:
    """In-memory storage of per-user notifications."""

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        """Store ``message`` for ``user_id`` and return the new note id."""
        note = self._build_notification(message)
        self.notifications.setdefault(user_id, []).append(note)
        return note['id']

    def get_notifications(self, user_id):
        """Return all notifications stored for ``user_id``."""
        return self.notifications.get(user_id, [])

    @staticmethod
    def _build_notification(message):
        """Create a notification record with a fresh id and timestamp."""
        return {
            'id': str(uuid.uuid4()),
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }


notification_system = NotificationSystem()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _serialize_notification(note):
    """Return a JSON-safe representation of a stored notification."""
    return {
        'id': note['id'],
        'message': note['message'],
        'timestamp': note['timestamp'],
    }


def _write_text_file(path, contents):
    """Write ``contents`` to ``path``, overwriting any existing file."""
    with open(path, 'w') as f:
        f.write(contents)


def _ensure_templates():
    """Create the template directory if needed and write the templates."""
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    _write_text_file(LOGIN_TEMPLATE_PATH, LOGIN_TEMPLATE)
    _write_text_file(MAIN_TEMPLATE_PATH, MAIN_TEMPLATE)


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------

class BaseHandler(tornado.web.RequestHandler):
    """Shared behaviour: the user cookie and the security headers."""

    def get_current_user(self):
        return self.get_secure_cookie(USER_COOKIE_NAME)

    def set_default_headers(self):
        for name, value in SECURITY_HEADERS:
            self.set_header(name, value)

    def _current_user_id(self):
        """Return the decoded id of the currently logged-in user."""
        return self.current_user.decode()


class MainHandler(BaseHandler):
    """Serve the main page to authenticated users."""

    def get(self):
        if not self.current_user:
            self.redirect(PATH_LOGIN)
            return
        self.render(MAIN_TEMPLATE_NAME, user=html.escape(self._current_user_id()))


class LoginHandler(BaseHandler):
    """Show the login form and establish the session cookie."""

    def get(self):
        self.render(LOGIN_TEMPLATE_NAME)

    def post(self):
        username = self.get_body_argument('username', '').strip()
        if not username:
            self.set_status(400)
            return
        self.set_secure_cookie(USER_COOKIE_NAME, username, **COOKIE_OPTIONS)
        self.redirect(PATH_MAIN)


class NotificationHandler(BaseHandler):
    """Accept and store a new notification for the current user."""

    def post(self):
        if not self.current_user:
            self.set_status(403)
            return
        user_id = self._current_user_id()
        message = self.get_body_argument('message', '')
        sanitized_message = html.escape(message)
        if not sanitized_message:
            self.set_status(400)
            return
        note_id = notification_system.add_notification(user_id, sanitized_message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):
    """Return the current user's notifications as a JSON array."""

    def get(self):
        if not self.current_user:
            self.set_status(403)
            return
        user_id = self._current_user_id()
        notes = notification_system.get_notifications(user_id)
        safe_notes = [_serialize_notification(note) for note in notes]
        self.set_header('Content-Type', CONTENT_TYPE_JSON)
        self.write(json.dumps(safe_notes))


# ---------------------------------------------------------------------------
# Application factory and entry point
# ---------------------------------------------------------------------------

ROUTES = [
    (PATH_MAIN, MainHandler),
    (PATH_LOGIN, LoginHandler),
    (PATH_NOTIFY, NotificationHandler),
    (PATH_GET_NOTIFICATIONS, GetNotificationsHandler),
]


def make_app():
    """Write the templates and return the configured Tornado application."""
    _ensure_templates()
    return tornado.web.Application(
        ROUTES,
        cookie_secret=secrets.token_urlsafe(COOKIE_SECRET_NBYTES),
        xsrf_cookies=True,
    )


def main():
    """Start the HTTP server (command-line entry point)."""
    app = make_app()
    app.listen(DEFAULT_PORT)
    print('Server started at http://localhost:{}'.format(DEFAULT_PORT))
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
