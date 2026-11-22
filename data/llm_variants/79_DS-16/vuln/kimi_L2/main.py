import tornado.ioloop
import tornado.web
import tornado.template
import os
import json
import uuid
from datetime import datetime

_COOKIE_NAME = 'user'
_COOKIE_SECRET = '__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__'

_ROOT_ROUTE = '/'
_LOGIN_ROUTE = '/login'
_NOTIFY_ROUTE = '/notify'
_GET_NOTIFICATIONS_ROUTE = '/get_notifications'

_TEMPLATES_DIR = 'templates'
_LOGIN_TEMPLATE_NAME = 'login.html'
_MAIN_TEMPLATE_NAME = 'main.html'
_LOGIN_TEMPLATE_PATH = 'templates/login.html'
_MAIN_TEMPLATE_PATH = 'templates/main.html'

_FORBIDDEN_STATUS = 403
_PORT = 8888

_LOGIN_HTML = '<!DOCTYPE html>\n<html>\n<head><title>Login</title></head>\n<body>\n    <form method="post">\n        <input type="text" name="username" placeholder="Username">\n        <button type="submit">Login</button>\n    </form>\n</body>\n</html>'
_MAIN_HTML = '<!DOCTYPE html>\n<html>\n<head>\n    <title>Notification System</title>\n    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>\n</head>\n<body>\n    <h1>Welcome, {{ user }}</h1>\n    \n    <div>\n        <h2>Send Notification</h2>\n        <textarea id="message" placeholder="Notification message"></textarea>\n        <button onclick="sendNotification()">Send</button>\n    </div>\n    \n    <div id="notifications"></div>\n    \n    <script>\n        function sendNotification() {\n            const message = $(\'#message\').val();\n            $.post(\'/notify\', {message: message}, function(data) {\n                loadNotifications();\n            });\n        }\n        \n        function loadNotifications() {\n            $.get(\'/get_notifications\', function(data) {\n                const notes = JSON.parse(data);\n                let html = \'<h2>Your Notifications</h2><ul>\';\n                notes.forEach(note => {\n\n                    html += `<li>${note.message} <small>${note.timestamp}</small></li>`;\n                });\n                html += \'</ul>\';\n                $(\'#notifications\').html(html);\n            });\n        }\n        \n        // Load notifications on page load\n        $(document).ready(loadNotifications);\n    </script>\n</body>\n</html>'

_TEMPLATE_FILES = (
    (_LOGIN_TEMPLATE_PATH, _LOGIN_HTML),
    (_MAIN_TEMPLATE_PATH, _MAIN_HTML),
)


def _ensure_templates_dir():
    if not os.path.exists(_TEMPLATES_DIR):
        os.makedirs(_TEMPLATES_DIR)


def _write_text_file(path, content):
    with open(path, 'w') as f:
        f.write(content)


def _write_default_templates():
    _ensure_templates_dir()
    for path, content in _TEMPLATE_FILES:
        _write_text_file(path, content)


def _application_settings():
    return {'cookie_secret': _COOKIE_SECRET}


class NotificationSystem:

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        if user_id not in self.notifications:
            self.notifications[user_id] = []
        note_id = str(uuid.uuid4())
        self.notifications[user_id].append({
            'id': note_id,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        })
        return note_id

    def get_notifications(self, user_id):
        return self.notifications.get(user_id, [])


notification_system = NotificationSystem()


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie(_COOKIE_NAME)


class MainHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.redirect(_LOGIN_ROUTE)
            return
        self.render(_MAIN_TEMPLATE_NAME, user=self.current_user.decode())


class LoginHandler(BaseHandler):

    def get(self):
        self.render(_LOGIN_TEMPLATE_NAME)

    def post(self):
        username = self.get_body_argument('username')
        self.set_secure_cookie(_COOKIE_NAME, username)
        self.redirect(_ROOT_ROUTE)


class NotificationHandler(BaseHandler):

    def post(self):
        if not self.current_user:
            self.set_status(_FORBIDDEN_STATUS)
            return
        user_id = self.current_user.decode()
        message = self.get_body_argument('message')
        note_id = notification_system.add_notification(user_id, message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.set_status(_FORBIDDEN_STATUS)
            return
        user_id = self.current_user.decode()
        notes = notification_system.get_notifications(user_id)
        self.write(json.dumps(notes))


def _routes():
    return [
        (_ROOT_ROUTE, MainHandler),
        (_LOGIN_ROUTE, LoginHandler),
        (_NOTIFY_ROUTE, NotificationHandler),
        (_GET_NOTIFICATIONS_ROUTE, GetNotificationsHandler),
    ]


def make_app():
    _write_default_templates()
    return tornado.web.Application(_routes(), **_application_settings())


if __name__ == '__main__':
    app = make_app()
    app.listen(_PORT)
    print('Server started at http://localhost:{}'.format(_PORT))
    tornado.ioloop.IOLoop.current().start()
