import tornado.ioloop
import tornado.web
import tornado.template
import os
import json
import uuid
from datetime import datetime

TEMPLATE_DIR = 'templates'
COOKIE_SECRET = '__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__'
PORT = 8888

LOGIN_HTML = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head><title>Login</title></head>\n'
    '<body>\n'
    '    <form method="post">\n'
    '        <input type="text" name="username" placeholder="Username">\n'
    '        <button type="submit">Login</button>\n'
    '    </form>\n'
    '</body>\n'
    '</html>'
)

MAIN_HTML = (
    '<!DOCTYPE html>\n'
    '<html>\n'
    '<head>\n'
    '    <title>Notification System</title>\n'
    '    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>\n'
    '</head>\n'
    '<body>\n'
    '    <h1>Welcome, {{ user }}</h1>\n'
    '    \n'
    '    <div>\n'
    '        <h2>Send Notification</h2>\n'
    '        <textarea id="message" placeholder="Notification message"></textarea>\n'
    '        <button onclick="sendNotification()">Send</button>\n'
    '    </div>\n'
    '    \n'
    '    <div id="notifications"></div>\n'
    '    \n'
    '    <script>\n'
    '        function sendNotification() {\n'
    "            const message = $('#message').val();\n"
    "            $.post('/notify', {message: message}, function(data) {\n"
    '                loadNotifications();\n'
    '            });\n'
    '        }\n'
    '        \n'
    '        function loadNotifications() {\n'
    "            $.get('/get_notifications', function(data) {\n"
    '                const notes = JSON.parse(data);\n'
    "                let html = '<h2>Your Notifications</h2><ul>';\n"
    '                notes.forEach(note => {\n'
    '\n'
    '                    html += `<li>${note.message} <small>${note.timestamp}</small></li>`;\n'
    '                });\n'
    "                html += '</ul>';\n"
    "                $('#notifications').html(html);\n"
    '            });\n'
    '        }\n'
    '        \n'
    '        // Load notifications on page load\n'
    '        $(document).ready(loadNotifications);\n'
    '    </script>\n'
    '</body>\n'
    '</html>'
)


class NotificationSystem:

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


def make_app():
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
    with open(os.path.join(TEMPLATE_DIR, 'login.html'), 'w') as f:
        f.write(LOGIN_HTML)
    with open(os.path.join(TEMPLATE_DIR, 'main.html'), 'w') as f:
        f.write(MAIN_HTML)
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
    app.listen(PORT)
    print('Server started at http://localhost:8888')
    tornado.ioloop.IOLoop.current().start()
