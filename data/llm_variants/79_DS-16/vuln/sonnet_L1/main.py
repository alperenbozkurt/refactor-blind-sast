import tornado.ioloop
import tornado.web
import tornado.template
import os
import json
import uuid
from datetime import datetime

TEMPLATES_DIR = 'templates'
SERVER_PORT = 8888
COOKIE_SECRET = '__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__'

LOGIN_TEMPLATE = "\n".join([
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

MAIN_TEMPLATE = "\n".join([
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


class NotificationSystem:
    """In-memory storage of notifications, keyed by user id."""

    def __init__(self):
        self.notifications = {}

    def add_notification(self, user_id, message):
        note_id = str(uuid.uuid4())
        note = {
            'id': note_id,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }
        self.notifications.setdefault(user_id, []).append(note)
        return note_id

    def get_notifications(self, user_id):
        return self.notifications.get(user_id, [])


notification_system = NotificationSystem()


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie('user')


class MainHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.redirect('/login')
            return
        self.render('main.html', user=self.current_user.decode())


class LoginHandler(BaseHandler):

    def get(self):
        self.render('login.html')

    def post(self):
        username = self.get_body_argument('username')
        self.set_secure_cookie('user', username)
        self.redirect('/')


class NotificationHandler(BaseHandler):

    def post(self):
        if not self.current_user:
            self.set_status(403)
            return
        user_id = self.current_user.decode()
        message = self.get_body_argument('message')
        note_id = notification_system.add_notification(user_id, message)
        self.write(json.dumps({'status': 'success', 'id': note_id}))


class GetNotificationsHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            self.set_status(403)
            return
        user_id = self.current_user.decode()
        notes = notification_system.get_notifications(user_id)
        self.write(json.dumps(notes))


def write_template(filename, content):
    path = os.path.join(TEMPLATES_DIR, filename)
    with open(path, 'w') as f:
        f.write(content)


def make_app():
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)

    write_template('login.html', LOGIN_TEMPLATE)
    write_template('main.html', MAIN_TEMPLATE)

    routes = [
        ('/', MainHandler),
        ('/login', LoginHandler),
        ('/notify', NotificationHandler),
        ('/get_notifications', GetNotificationsHandler),
    ]
    return tornado.web.Application(routes, cookie_secret=COOKIE_SECRET)


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    print('Server started at http://localhost:8888')
    tornado.ioloop.IOLoop.current().start()
