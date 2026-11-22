import cherrypy
import os
import sqlite3
import html
from datetime import datetime
import secrets

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DB_PATH = 'feedback.db'

MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000

CSRF_SESSION_KEY = '_csrf_token'
CSRF_TOKEN_BYTES = 32

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080
SESSION_STORAGE_TYPE = 'file'
SESSION_STORAGE_PATH = './sessions'
SESSION_SECRET_BYTES = 64
SESSION_TIMEOUT_MINUTES = 60
STATIC_DIR = './public'

SECURITY_HEADERS = {
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'X-Content-Type-Options': 'nosniff',
    'Content-Security-Policy': "default-src 'self'",
}

CREATE_TABLE_SQL = """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """

INSERT_FEEDBACK_SQL = """
            INSERT INTO feedback (name, message) VALUES (?, ?)
        """

SELECT_ALL_FEEDBACK_SQL = 'SELECT * FROM feedback ORDER BY timestamp DESC'


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

class FeedbackSystem:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
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


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------

def render_feedback_item(item):
    return f"""
                <div class="feedback-item">
                    <h3>{item[1]}</h3>  <!-- Already escaped in storage -->
                    <p>{item[2]}</p>     <!-- Already escaped in storage -->
                    <small>{item[3]}</small>
                </div>
            """


def render_feedback_list(feedback_list):
    return ''.join(render_feedback_item(item) for item in feedback_list)


def render_page(csrf_token, feedback_html):
    return f"""
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
                        <input type="text" name="name" required maxlength="{MAX_NAME_LENGTH}">
                    </p>
                    <p>
                        <label>Your Feedback:</label><br>
                        <textarea name="message" required maxlength="{MAX_MESSAGE_LENGTH}"></textarea>
                    </p>
                    <button type="submit">Submit Feedback</button>
                </form>
                
                <h2>Recent Feedback</h2>
                {feedback_html}
            </body>
            </html>
        """


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------

def _validate_csrf_token(token):
    if not token or token != cherrypy.session.get(CSRF_SESSION_KEY):
        raise cherrypy.HTTPError(403, 'Invalid CSRF token')


def _validate_feedback_input(name, message):
    if not name or not message:
        raise cherrypy.HTTPError(400, 'Name and message are required')
    if len(name) > MAX_NAME_LENGTH or len(message) > MAX_MESSAGE_LENGTH:
        raise cherrypy.HTTPError(400, 'Input too long')


# --------------------------------------------------------------------------
# Web application
# --------------------------------------------------------------------------

class Root:

    @cherrypy.expose
    def index(self):
        feedback_list = feedback_system.get_all_feedback()
        feedback_html = render_feedback_list(feedback_list)
        return render_page(self.get_csrf_token(), feedback_html)

    def get_csrf_token(self):
        if not cherrypy.session.get(CSRF_SESSION_KEY):
            cherrypy.session[CSRF_SESSION_KEY] = secrets.token_urlsafe(CSRF_TOKEN_BYTES)
        return cherrypy.session[CSRF_SESSION_KEY]

    @cherrypy.expose
    def submit_feedback(self, name, message, _csrf_token=None):
        _validate_csrf_token(_csrf_token)
        _validate_feedback_input(name, message)
        feedback_system.add_feedback(name, message)
        raise cherrypy.HTTPRedirect('/')


def secureheaders():
    headers = cherrypy.response.headers
    for header_name, header_value in SECURITY_HEADERS.items():
        headers[header_name] = header_value


# --------------------------------------------------------------------------
# Configuration / entry point
# --------------------------------------------------------------------------

def build_app_config():
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


def build_global_config():
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
    cherrypy.config.update(build_global_config())
    cherrypy.tools.secureheaders = cherrypy.Tool('before_finalize', secureheaders)
    cherrypy.quickstart(Root(), '/', conf)


if __name__ == '__main__':
    main()
