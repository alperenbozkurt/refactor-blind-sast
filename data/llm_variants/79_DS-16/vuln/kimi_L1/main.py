"""A minimal per-user notification system built on Tornado.

Running this module directly starts the development server on port 8888.
"""

import json
import os
import uuid
from datetime import datetime

import tornado.ioloop
import tornado.template
import tornado.web

# Directory, relative to the working directory, where the HTML templates
# are (re)written each time the application is created.
TEMPLATE_DIR = 'templates'

# Name of the secure cookie that stores the logged-in user's name.
USER_COOKIE = 'user'

# Secret used to sign the secure cookies.
COOKIE_SECRET = '__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__'

# Port the development server listens on.
SERVER_PORT = 8888

LOGIN_TEMPLATE = """<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
    <form method="post">
        <input type="text" name="username" placeholder="Username">
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
        <textarea id="message" placeholder="Notification message"></textarea>
        <button onclick="sendNotification()">Send</button>
    </div>
    
    <div id="notifications"></div>
    
    <script>
        function sendNotification() {
            const message = $('#message').val();
            $.post('/notify', {message: message}, function(data) {
                loadNotifications();
            });
        }
        
        function loadNotifications() {
            $.get('/get_notifications', function(data) {
                const notes = JSON.parse(data);
                let html = '<h2>Your Notifications</h2><ul>';
                notes.forEach(note => {

                    html += `<li>${note.message} <small>${note.timestamp}</small></li>`;
                });
                html += '</ul>';
                $('#notifications').html(html);
            });
        }
        
        // Load notifications on page load
        $(document).ready(loadNotifications);
    </script>
</body>
</html>"""

# Templates written to TEMPLATE_DIR by make_app(), in write order.
TEMPLATES = {
    'login.html': LOGIN_TEMPLATE,
    'main.html': MAIN_TEMPLATE,
}


class NotificationSystem:
    """In-memory store of notifications, grouped by user id."""

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        """Store ``message`` for ``user_id`` and return the new note id."""
        note = {
            'id': str(uuid.uuid4()),
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }
        self.notifications.setdefault(user_id, []).append(note)
        return note['id']

    def get_notifications(self, user_id):
        """Return the list of notifications stored for ``user_id``."""
        return self.notifications.get(user_id, [])


notification_system = NotificationSystem()


class BaseHandler(tornado.web.RequestHandler):
    """Common base providing cookie-based authentication helpers."""

    def get_current_user(self):
        return self.get_secure_cookie(USER_COOKIE)

    def _authenticated_user_id(self):
        """Return the decoded id of the logged-in user.

        If no user is logged in, respond with status 403 and return None.
        """
        if not self.current_user:
            self.set_status(403)
            return None
        return self.current_user.decode()


class MainHandler(BaseHandler):
    """Render the main page, redirecting anonymous users to the login page."""

    def get(self):
        if not self.current_user:
            self.redirect('/login')
            return
        self.render('main.html', user=self.current_user.decode())


class LoginHandler(BaseHandler):
    """Show the login form and log users in."""

    def get(self):
        self.render('login.html')

    def post(self):
        username = self.get_body_argument('username')
        self.set_secure_cookie(USER_COOKIE, username)
        self.redirect('/')


class NotificationHandler(BaseHandler):
    """Create a notification for the logged-in user."""

    def post(self):
        user_id = self._authenticated_user_id()
        if user_id is None:
            return
        message = self.get_body_argument('message')
        note_id = notification_system.add_notification(user_id, message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):
    """Return the notifications of the logged-in user as JSON."""

    def get(self):
        user_id = self._authenticated_user_id()
        if user_id is None:
            return
        notes = notification_system.get_notifications(user_id)
        self.write(json.dumps(notes))


def _write_templates():
    """Create TEMPLATE_DIR if needed and (re)write the default templates."""
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
    for filename, content in TEMPLATES.items():
        path = os.path.join(TEMPLATE_DIR, filename)
        with open(path, 'w') as template_file:
            template_file.write(content)


def make_app():
    """Write the default templates and return the Tornado application."""
    _write_templates()
    return tornado.web.Application(
        [
            ('/', MainHandler),
            ('/login', LoginHandler),
            ('/notify', NotificationHandler),
            ('/get_notifications', GetNotificationsHandler),
        ],
        cookie_secret=COOKIE_SECRET,
    )


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    print(f'Server started at http://localhost:{SERVER_PORT}')
    tornado.ioloop.IOLoop.current().start()
