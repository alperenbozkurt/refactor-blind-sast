import html
import json
import os
import secrets
import uuid
from datetime import datetime

import tornado.ioloop
import tornado.template
import tornado.web

TEMPLATES_DIR = 'templates'
SERVER_PORT = 8888

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


class NotificationSystem:
    """In-memory store of notifications, keyed by user id."""

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
        message = self.get_body_argument('message', '')
        sanitized_message = html.escape(message)
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
        notes = notification_system.get_notifications(user_id)
        safe_notes = [
            {
                'id': note['id'],
                'message': note['message'],
                'timestamp': note['timestamp'],
            }
            for note in notes
        ]
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(safe_notes))


def _write_template(filename, content):
    path = os.path.join(TEMPLATES_DIR, filename)
    with open(path, 'w') as f:
        f.write(content)


def _write_templates():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    _write_template('login.html', LOGIN_TEMPLATE)
    _write_template('main.html', MAIN_TEMPLATE)


def make_app():
    _write_templates()
    cookie_secret = secrets.token_urlsafe(64)
    routes = [
        ('/', MainHandler),
        ('/login', LoginHandler),
        ('/notify', NotificationHandler),
        ('/get_notifications', GetNotificationsHandler),
    ]
    return tornado.web.Application(routes, cookie_secret=cookie_secret, xsrf_cookies=True)


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    print('Server started at http://localhost:8888')
    tornado.ioloop.IOLoop.current().start()
