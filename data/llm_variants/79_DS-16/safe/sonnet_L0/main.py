import tornado.ioloop
import tornado.web
import tornado.template
import os
import json
import uuid
from datetime import datetime
import html
import secrets

LOGIN_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head>\n'
    '    <title>Login</title>\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '</head>\n'
    '<body>\n'
    '    <form method="post">\n'
    '        <input type="text" name="username" placeholder="Username" required>\n'
    '        <button type="submit">Login</button>\n'
    '    </form>\n'
    '</body>\n'
    '</html>'
)

MAIN_TEMPLATE = (
    '<!DOCTYPE html>\n<html>\n<head>\n    <title>Notification System</title>\n    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>\n</head>\n<body>\n    <h1>Welcome, {{ user }}</h1>\n    \n    <div>\n        <h2>Send Notification</h2>\n        <textarea id="message" placeholder="Notification message" required></textarea>\n        <button onclick="sendNotification()">Send</button>\n    </div>\n    \n    <div id="notifications"></div>\n    \n    <script>\n        function escapeHtml(text) {\n            const div = document.createElement(\'div\');\n            div.textContent = text;\n            return div.innerHTML;\n        }\n        \n        function sendNotification() {\n            const message = $(\'#message\').val();\n            if (!message) return;\n            \n            $.post(\'/notify\', {message: message}, function(data) {\n                $(\'#message\').val(\'\');\n                loadNotifications();\n            });\n        }\n        \n        function loadNotifications() {\n            $.get(\'/get_notifications\', function(data) {\n                try {\n                    const notes = JSON.parse(data);\n                    let html = \'<h2>Your Notifications</h2><ul>\';\n                    notes.forEach(note => {\n                        // Fixed: Use textContent or proper escaping\n                        html += `<li>${escapeHtml(note.message)} <small>${escapeHtml(note.timestamp)}</small></li>`;\n                    });\n                    html += \'</ul>\';\n                    $(\'#notifications\').html(html);\n                } catch (e) {\n                    console.error(\'Error loading notifications:\', e);\n                }\n            });\n        }\n        \n        // Load notifications on page load\n        $(document).ready(loadNotifications);\n    </script>\n</body>\n</html>'
)


class NotificationSystem:

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        note_id = str(uuid.uuid4())
        self.notifications.setdefault(user_id, []).append({
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
        return self.get_secure_cookie('user')

    def set_default_headers(self):
        self.set_header('X-Content-Type-Options', 'nosniff')
        self.set_header('X-Frame-Options', 'DENY')
        self.set_header('X-XSS-Protection', '1; mode=block')
        self.set_header('Content-Security-Policy', "default-src 'self'")


class MainHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.redirect('/login')
            return
        self.render('main.html', user=html.escape(self.current_user.decode()))


class LoginHandler(BaseHandler):

    def get(self):
        self.render('login.html')

    def post(self):
        username = self.get_body_argument('username', '').strip()
        if not username:
            self.set_status(400)
            return
        self.set_secure_cookie('user', username, httponly=True, secure=True, samesite='Lax')
        self.redirect('/')


class NotificationHandler(BaseHandler):

    def post(self):
        if not self.current_user:
            self.set_status(403)
            return
        user_id = self.current_user.decode()
        sanitized_message = html.escape(self.get_body_argument('message', ''))
        if not sanitized_message:
            self.set_status(400)
            return
        note_id = notification_system.add_notification(user_id, sanitized_message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.set_status(403)
            return
        user_id = self.current_user.decode()
        safe_notes = [
            {'id': note['id'], 'message': note['message'], 'timestamp': note['timestamp']}
            for note in notification_system.get_notifications(user_id)
        ]
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(safe_notes))


def _write_template(name, content):
    with open(os.path.join('templates', name), 'w') as f:
        f.write(content)


def make_app():
    if not os.path.exists('templates'):
        os.makedirs('templates')
    _write_template('login.html', LOGIN_TEMPLATE)
    _write_template('main.html', MAIN_TEMPLATE)
    cookie_secret = secrets.token_urlsafe(64)
    return tornado.web.Application(
        [
            ('/', MainHandler),
            ('/login', LoginHandler),
            ('/notify', NotificationHandler),
            ('/get_notifications', GetNotificationsHandler),
        ],
        cookie_secret=cookie_secret,
        xsrf_cookies=True,
    )


if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    print('Server started at http://localhost:8888')
    tornado.ioloop.IOLoop.current().start()
