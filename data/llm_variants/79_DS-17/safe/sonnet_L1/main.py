import cherrypy
import os
import sqlite3
import html
from datetime import datetime
import secrets


DATABASE_PATH = 'feedback.db'

CREATE_TABLE_SQL = '''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        '''

INSERT_FEEDBACK_SQL = '''
            INSERT INTO feedback (name, message) VALUES (?, ?)
        '''

SELECT_ALL_FEEDBACK_SQL = 'SELECT * FROM feedback ORDER BY timestamp DESC'

MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000

FEEDBACK_ITEM_TEMPLATE = '''
                <div class="feedback-item">
                    <h3>{name}</h3>  <!-- Already escaped in storage -->
                    <p>{message}</p>     <!-- Already escaped in storage -->
                    <small>{timestamp}</small>
                </div>
            '''

PAGE_TEMPLATE = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Feedback System</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .feedback-item {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; }}
                    textarea {{ width: 100%; height: 100px; }}
                </style>
            </head>
            <body>
                <h1>Customer Feedback</h1>
                
                <form method="post" action="/submit_feedback">
                    <input type="hidden" name="_csrf_token" value="{csrf_token}">
                    <h2>Submit Your Feedback</h2>
                    <p>
                        <label>Your Name:</label><br>
                        <input type="text" name="name" required maxlength="100">
                    </p>
                    <p>
                        <label>Your Feedback:</label><br>
                        <textarea name="message" required maxlength="2000"></textarea>
                    </p>
                    <button type="submit">Submit Feedback</button>
                </form>
                
                <h2>Recent Feedback</h2>
                {feedback_html}
            </body>
            </html>
        '''


class FeedbackSystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)
        self.conn.commit()

    def add_feedback(self, name, message):
        sanitized_name = html.escape(name)
        sanitized_message = html.escape(message)
        cursor = self.conn.cursor()
        cursor.execute(INSERT_FEEDBACK_SQL, (sanitized_name, sanitized_message))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_feedback(self):
        cursor = self.conn.cursor()
        cursor.execute(SELECT_ALL_FEEDBACK_SQL)
        return cursor.fetchall()


feedback_system = FeedbackSystem()


class Root:

    @staticmethod
    def _render_feedback_item(item):
        # Values are already escaped when stored.
        return FEEDBACK_ITEM_TEMPLATE.format(
            name=item[1],
            message=item[2],
            timestamp=item[3],
        )

    @cherrypy.expose
    def index(self):
        feedback_list = feedback_system.get_all_feedback()
        feedback_html = ''.join(
            self._render_feedback_item(item) for item in feedback_list
        )
        return PAGE_TEMPLATE.format(
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
    app_conf = {
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
    conf = app_conf

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
