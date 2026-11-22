import cherrypy
import os
import sqlite3
import html
from datetime import datetime
import secrets

# ---------------------------------------------------------------------------
# Application constants
# ---------------------------------------------------------------------------

DATABASE_PATH = 'feedback.db'

MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000

CSRF_SESSION_KEY = '_csrf_token'
CSRF_TOKEN_BYTES = 32
SESSION_SECRET_BYTES = 64

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080
STATIC_DIR = './public'
SESSION_STORAGE_TYPE = 'file'
SESSION_STORAGE_PATH = './sessions'
SESSION_TIMEOUT_MINUTES = 60

ERROR_INVALID_CSRF = 'Invalid CSRF token'
ERROR_MISSING_INPUT = 'Name and message are required'
ERROR_INPUT_TOO_LONG = 'Input too long'

# SQL statements.

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

# HTML templates.

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

# Security headers applied to every response (insertion order is preserved).

SECURITY_HEADERS = {
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'X-Content-Type-Options': 'nosniff',
    'Content-Security-Policy': "default-src 'self'",
}


def _sanitize(text):
    """Escape user supplied text so it is safe to embed in HTML."""
    return html.escape(text)


def _render_feedback_item(item):
    """Render a single feedback row as an HTML fragment."""
    return FEEDBACK_ITEM_TEMPLATE.format(
        name=item[1],
        message=item[2],
        timestamp=item[3],
    )


def _render_feedback_list(feedback_list):
    """Render a sequence of feedback rows as one HTML fragment."""
    return ''.join(_render_feedback_item(item) for item in feedback_list)


class FeedbackSystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)
        self.conn.commit()

    def add_feedback(self, name, message):
        sanitized_name = _sanitize(name)
        sanitized_message = _sanitize(message)
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

    @cherrypy.expose
    def index(self):
        feedback_html = _render_feedback_list(feedback_system.get_all_feedback())
        return PAGE_TEMPLATE.format(
            csrf_token=self.get_csrf_token(),
            feedback_html=feedback_html,
        )

    def get_csrf_token(self):
        if not cherrypy.session.get(CSRF_SESSION_KEY):
            cherrypy.session[CSRF_SESSION_KEY] = secrets.token_urlsafe(CSRF_TOKEN_BYTES)
        return cherrypy.session[CSRF_SESSION_KEY]

    @cherrypy.expose
    def submit_feedback(self, name, message, _csrf_token=None):
        if not _csrf_token or _csrf_token != cherrypy.session.get(CSRF_SESSION_KEY):
            raise cherrypy.HTTPError(403, ERROR_INVALID_CSRF)
        if not name or not message:
            raise cherrypy.HTTPError(400, ERROR_MISSING_INPUT)
        if len(name) > MAX_NAME_LENGTH or len(message) > MAX_MESSAGE_LENGTH:
            raise cherrypy.HTTPError(400, ERROR_INPUT_TOO_LONG)
        feedback_system.add_feedback(name, message)
        raise cherrypy.HTTPRedirect('/')


def secureheaders():
    headers = cherrypy.response.headers
    for header, value in SECURITY_HEADERS.items():
        headers[header] = value


def build_app_config():
    """Return the per-path CherryPy configuration."""
    return {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
            'tools.secureheaders.on': True,
            'tools.sessions.secure': True,
            'tools.sessions.httponly': True,
            'tools.sessions.timeout': SESSION_TIMEOUT_MINUTES,
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': STATIC_DIR,
        },
    }


def build_server_config():
    """Return the global CherryPy server configuration."""
    return {
        'server.socket_host': SERVER_HOST,
        'server.socket_port': SERVER_PORT,
        'tools.sessions.storage_type': SESSION_STORAGE_TYPE,
        'tools.sessions.storage_path': SESSION_STORAGE_PATH,
        'tools.sessions.secret': secrets.token_urlsafe(SESSION_SECRET_BYTES),
        'tools.secureheaders.on': True,
    }


def main():
    conf = build_app_config()
    cherrypy.config.update(build_server_config())
    cherrypy.tools.secureheaders = cherrypy.Tool('before_finalize', secureheaders)
    cherrypy.quickstart(Root(), '/', conf)


if __name__ == '__main__':
    main()
