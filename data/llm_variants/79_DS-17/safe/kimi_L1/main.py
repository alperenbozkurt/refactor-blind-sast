"""Customer feedback web application built with CherryPy and SQLite."""

import html
import os
import secrets
import sqlite3
from datetime import datetime

import cherrypy

DATABASE_PATH = 'feedback.db'
MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000
CSRF_SESSION_KEY = '_csrf_token'


class FeedbackSystem:
    """SQLite-backed storage for customer feedback entries."""

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.create_table()

    def create_table(self):
        """Create the feedback table if it does not already exist."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def add_feedback(self, name, message):
        """HTML-escape and store a feedback entry, returning its row id."""
        sanitized_name = html.escape(name)
        sanitized_message = html.escape(message)
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO feedback (name, message) VALUES (?, ?)
        ''', (sanitized_name, sanitized_message))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_feedback(self):
        """Return all feedback rows, newest first."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM feedback ORDER BY timestamp DESC')
        return cursor.fetchall()


feedback_system = FeedbackSystem()


class Root:
    """CherryPy root handler for the feedback pages."""

    @cherrypy.expose
    def index(self):
        """Render the submission form and the stored feedback entries."""
        feedback_html = ''.join(
            self._render_feedback_item(item)
            for item in feedback_system.get_all_feedback()
        )
        csrf_token = self.get_csrf_token()
        return f'''
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
        '''

    @staticmethod
    def _render_feedback_item(item):
        """Render a single feedback row (fields are already escaped)."""
        _, name, message, timestamp = item
        return f'''
                <div class="feedback-item">
                    <h3>{name}</h3>  <!-- Already escaped in storage -->
                    <p>{message}</p>     <!-- Already escaped in storage -->
                    <small>{timestamp}</small>
                </div>
            '''

    def get_csrf_token(self):
        """Return the session CSRF token, generating it on first use."""
        if not cherrypy.session.get(CSRF_SESSION_KEY):
            cherrypy.session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
        return cherrypy.session[CSRF_SESSION_KEY]

    @cherrypy.expose
    def submit_feedback(self, name, message, _csrf_token=None):
        """Validate and store a submission, then redirect to the index."""
        if not _csrf_token or _csrf_token != cherrypy.session.get(CSRF_SESSION_KEY):
            raise cherrypy.HTTPError(403, 'Invalid CSRF token')
        if not name or not message:
            raise cherrypy.HTTPError(400, 'Name and message are required')
        if len(name) > MAX_NAME_LENGTH or len(message) > MAX_MESSAGE_LENGTH:
            raise cherrypy.HTTPError(400, 'Input too long')
        feedback_system.add_feedback(name, message)
        raise cherrypy.HTTPRedirect('/')


def secureheaders():
    """Add security-related headers to the response."""
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
