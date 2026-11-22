"""A minimal in-memory notification system built with Tornado."""

import html
import json
import os
import secrets
import uuid
from datetime import datetime

import tornado.ioloop
import tornado.web

TEMPLATES_DIR = 'templates'
USER_COOKIE = 'user'
PORT = 8888

LOGIN_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <form method="post">
        <input type="text" name="username" placeholder="Username" required>
        <button type="submit">Login</button>
    </form>
</body>
</html>"""

MAIN_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Notification System</title>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
</head>
<body>
    <h1>Welcome, {{ user }}</h1>
    
    <div>
        <h2>Send Notification</h2>
        <textarea id="message" placeholder="Notification message" required></textarea>
        <button onclick="sendNotification()">Send</button>
    </div>
    
    <div id="notifications"></div>
    
    <script>
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function sendNotification() {
            const message = $('#message').val();
            if (!message) return;
            
            $.post('/notify', {message: message}, function(data) {
                $('#message').val('');
                loadNotifications();
            });
        }
        
        function loadNotifications() {
            $.get('/get_notifications', function(data) {
                try {
                    const notes = JSON.parse(data);
                    let html = '<h2>Your Notifications</h2><ul>';
                    notes.forEach(note => {
                        // Fixed: Use textContent or proper escaping
                        html += `<li>${escapeHtml(note.message)} <small>${escapeHtml(note.timestamp)}</small></li>`;
                    });
                    html += '</ul>';
                    $('#notifications').html(html);
                } catch (e) {
                    console.error('Error loading notifications:', e);
                }
            });
        }
        
        // Load notifications on page load
        $(document).ready(loadNotifications);
    </script>
</body>
</html>"""

TEMPLATES = {
    'login.html': LOGIN_TEMPLATE,
    'main.html': MAIN_TEMPLATE,
}


class NotificationSystem:
    """Stores notifications for each user in memory."""

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        """Store *message* for *user_id* and return the new note's id."""
        note = {
            'id': str(uuid.uuid4()),
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }
        self.notifications.setdefault(user_id, []).append(note)
        return note['id']

    def get_notifications(self, user_id):
        """Return every notification stored for *user_id*."""
        return self.notifications.get(user_id, [])


notification_system = NotificationSystem()


class BaseHandler(tornado.web.RequestHandler):
    """Shared behaviour: security headers and cookie-based authentication."""

    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Content-Security-Policy': "default-src 'self'",
    }

    def get_current_user(self):
        return self.get_secure_cookie(USER_COOKIE)

    def set_default_headers(self):
        for header, value in self.SECURITY_HEADERS.items():
            self.set_header(header, value)

    def _authenticated_user_id(self):
        """Return the decoded name of the logged-in user, or None."""
        if not self.current_user:
            return None
        return self.current_user.decode()


class MainHandler(BaseHandler):

    def get(self):
        user_id = self._authenticated_user_id()
        if user_id is None:
            self.redirect('/login')
            return
        self.render('main.html', user=html.escape(user_id))


class LoginHandler(BaseHandler):

    def get(self):
        self.render('login.html')

    def post(self):
        username = self.get_body_argument('username', '').strip()
        if not username:
            self.set_status(400)
            return
        self.set_secure_cookie(USER_COOKIE, username, httponly=True, secure=True, samesite='Lax')
        self.redirect('/')


class NotificationHandler(BaseHandler):

    def post(self):
        user_id = self._authenticated_user_id()
        if user_id is None:
            self.set_status(403)
            return
        sanitized_message = html.escape(self.get_body_argument('message', ''))
        if not sanitized_message:
            self.set_status(400)
            return
        note_id = notification_system.add_notification(user_id, sanitized_message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):

    def get(self):
        user_id = self._authenticated_user_id()
        if user_id is None:
            self.set_status(403)
            return
        safe_notes = [
            {
                'id': note['id'],
                'message': note['message'],
                'timestamp': note['timestamp'],
            }
            for note in notification_system.get_notifications(user_id)
        ]
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(safe_notes))


ROUTES = [
    ('/', MainHandler),
    ('/login', LoginHandler),
    ('/notify', NotificationHandler),
    ('/get_notifications', GetNotificationsHandler),
]


def _write_templates():
    """Create the template directory and write the template files."""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    for filename, content in TEMPLATES.items():
        with open(os.path.join(TEMPLATES_DIR, filename), 'w') as f:
            f.write(content)


def make_app():
    _write_templates()
    return tornado.web.Application(
        ROUTES,
        cookie_secret=secrets.token_urlsafe(64),
        xsrf_cookies=True,
    )


def main():
    app = make_app()
    app.listen(PORT)
    print(f'Server started at http://localhost:{PORT}')
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
