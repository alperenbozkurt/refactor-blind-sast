import cherrypy
import os
import sqlite3
import html
from datetime import datetime
import secrets

_CREATE_TABLE_SQL = (
    '\n            CREATE TABLE IF NOT EXISTS feedback (\n'
    '                id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                name TEXT NOT NULL,\n'
    '                message TEXT NOT NULL,\n'
    '                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP\n'
    '            )\n        '
)
_INSERT_SQL = '\n            INSERT INTO feedback (name, message) VALUES (?, ?)\n        '
_SELECT_ALL_SQL = 'SELECT * FROM feedback ORDER BY timestamp DESC'


class FeedbackSystem:

    def __init__(self):
        self.conn = sqlite3.connect('feedback.db')
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute(_CREATE_TABLE_SQL)
        self.conn.commit()

    def add_feedback(self, name, message):
        sanitized_name = html.escape(name)
        sanitized_message = html.escape(message)
        cursor = self.conn.cursor()
        cursor.execute(_INSERT_SQL, (sanitized_name, sanitized_message))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_feedback(self):
        cursor = self.conn.cursor()
        cursor.execute(_SELECT_ALL_SQL)
        return cursor.fetchall()


feedback_system = FeedbackSystem()

_FEEDBACK_ITEM_TEMPLATE = (
    '\n                <div class="feedback-item">\n'
    '                    <h3>{name}</h3>  <!-- Already escaped in storage -->\n'
    '                    <p>{message}</p>     <!-- Already escaped in storage -->\n'
    '                    <small>{timestamp}</small>\n'
    '                </div>\n            '
)

_PAGE_TEMPLATE = (
    '\n            <!DOCTYPE html>\n'
    '            <html>\n'
    '            <head>\n'
    '                <title>Feedback System</title>\n'
    '                <meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '                <style>\n'
    '                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}\n'
    '                    .feedback-item {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; }}\n'
    '                    textarea {{ width: 100%; height: 100px; }}\n'
    '                </style>\n'
    '            </head>\n'
    '            <body>\n'
    '                <h1>Customer Feedback</h1>\n'
    '                \n'
    '                <form method="post" action="/submit_feedback">\n'
    '                    <input type="hidden" name="_csrf_token" value="{csrf_token}">\n'
    '                    <h2>Submit Your Feedback</h2>\n'
    '                    <p>\n'
    '                        <label>Your Name:</label><br>\n'
    '                        <input type="text" name="name" required maxlength="100">\n'
    '                    </p>\n'
    '                    <p>\n'
    '                        <label>Your Feedback:</label><br>\n'
    '                        <textarea name="message" required maxlength="2000"></textarea>\n'
    '                    </p>\n'
    '                    <button type="submit">Submit Feedback</button>\n'
    '                </form>\n'
    '                \n'
    '                <h2>Recent Feedback</h2>\n'
    '                {feedback_html}\n'
    '            </body>\n'
    '            </html>\n        '
)

MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000


def _render_feedback_items(feedback_list):
    return ''.join(
        _FEEDBACK_ITEM_TEMPLATE.format(name=item[1], message=item[2], timestamp=item[3])
        for item in feedback_list
    )


class Root:

    @cherrypy.expose
    def index(self):
        feedback_list = feedback_system.get_all_feedback()
        feedback_html = _render_feedback_items(feedback_list)
        return _PAGE_TEMPLATE.format(
            csrf_token=self.get_csrf_token(),
            feedback_html=feedback_html,
        )

    def get_csrf_token(self):
        if not cherrypy.session.get('_csrf_token'):
            cherrypy.session['_csrf_token'] = secrets.token_urlsafe(32)
        return cherrypy.session['_csrf_token']

    @cherrypy.expose
    def submit_feedback(self, name, message, _csrf_token=None):
        if not _csrf_token or _csrf_token != cherrypy.session.get('_csrf_token'):
            raise cherrypy.HTTPError(403, 'Invalid CSRF token')
        if not name or not message:
            raise cherrypy.HTTPError(400, 'Name and message are required')
        if len(name) > MAX_NAME_LENGTH or len(message) > MAX_MESSAGE_LENGTH:
            raise cherrypy.HTTPError(400, 'Input too long')
        feedback_system.add_feedback(name, message)
        raise cherrypy.HTTPRedirect('/')


def secureheaders():
    headers = cherrypy.response.headers
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['Content-Security-Policy'] = "default-src 'self'"


if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
            'tools.secureheaders.on': True,
            'tools.sessions.secure': True,
            'tools.sessions.httponly': True,
            'tools.sessions.timeout': 60,
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './public',
        },
    }
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080,
        'tools.sessions.storage_type': 'file',
        'tools.sessions.storage_path': './sessions',
        'tools.sessions.secret': secrets.token_urlsafe(64),
        'tools.secureheaders.on': True,
    })
    cherrypy.tools.secureheaders = cherrypy.Tool('before_finalize', secureheaders)
    cherrypy.quickstart(Root(), '/', conf)
