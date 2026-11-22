import cherrypy
import os
import sqlite3
import html
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'feedback.db'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080
MOUNT_PATH = '/'
STATIC_URL = '/static'
STATIC_DIR = './public'
REDIRECT_URL = '/'

CREATE_TABLE_SQL = (
    '\n            CREATE TABLE IF NOT EXISTS feedback ('
    '\n                id INTEGER PRIMARY KEY AUTOINCREMENT,'
    '\n                name TEXT NOT NULL,'
    '\n                message TEXT NOT NULL,'
    '\n                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP'
    '\n            )'
    '\n        '
)
INSERT_FEEDBACK_SQL = (
    '\n            INSERT INTO feedback (name, message) VALUES (?, ?)'
    '\n        '
)
SELECT_ALL_FEEDBACK_SQL = 'SELECT * FROM feedback ORDER BY timestamp DESC'

# Column indexes of the "feedback" table rows.
COL_NAME = 1
COL_MESSAGE = 2
COL_TIMESTAMP = 3

FEEDBACK_ITEM_TEMPLATE = (
    '\n                <div class="feedback-item">'
    '\n                    <h3>{name}</h3>'
    '\n                    <p>{message}</p>'
    '\n                    <small>{timestamp}</small>'
    '\n                </div>'
    '\n            '
)

FEEDBACK_PLACEHOLDER = '{feedback_html}'

PAGE_TEMPLATE = (
    '\n            <!DOCTYPE html>'
    '\n            <html>'
    '\n            <head>'
    '\n                <title>Feedback System</title>'
    '\n                <style>'
    '\n                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }'
    '\n                    .feedback-item { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; }'
    '\n                    textarea { width: 100%; height: 100px; }'
    '\n                </style>'
    '\n            </head>'
    '\n            <body>'
    '\n                <h1>Customer Feedback</h1>'
    '\n                '
    '\n                <form method="post" action="/submit_feedback">'
    '\n                    <h2>Submit Your Feedback</h2>'
    '\n                    <p>'
    '\n                        <label>Your Name:</label><br>'
    '\n                        <input type="text" name="name" required>'
    '\n                    </p>'
    '\n                    <p>'
    '\n                        <label>Your Feedback:</label><br>'
    '\n                        <textarea name="message" required></textarea>'
    '\n                    </p>'
    '\n                    <button type="submit">Submit Feedback</button>'
    '\n                </form>'
    '\n                '
    '\n                <h2>Recent Feedback</h2>'
    '\n                ' + FEEDBACK_PLACEHOLDER +
    '\n            </body>'
    '\n            </html>'
    '\n        '
)


# ---------------------------------------------------------------------------
# Persistence layer
# ---------------------------------------------------------------------------

class FeedbackSystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)
        self.conn.commit()

    def add_feedback(self, name, message):
        cursor = self.conn.cursor()
        cursor.execute(INSERT_FEEDBACK_SQL, (name, message))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_feedback(self):
        cursor = self.conn.cursor()
        cursor.execute(SELECT_ALL_FEEDBACK_SQL)
        return cursor.fetchall()


feedback_system = FeedbackSystem()


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_feedback_item(item):
    # NOTE: the message is intentionally rendered without escaping to keep
    # the original behaviour exactly unchanged.
    return FEEDBACK_ITEM_TEMPLATE.format(
        name=html.escape(item[COL_NAME]),
        message=item[COL_MESSAGE],
        timestamp=item[COL_TIMESTAMP],
    )


def _render_feedback_list(feedback_list):
    return ''.join(_render_feedback_item(item) for item in feedback_list)


def _render_page(feedback_html):
    return PAGE_TEMPLATE.replace(FEEDBACK_PLACEHOLDER, feedback_html)


# ---------------------------------------------------------------------------
# Web application
# ---------------------------------------------------------------------------

class Root:

    @cherrypy.expose
    def index(self):
        feedback_list = feedback_system.get_all_feedback()
        return _render_page(_render_feedback_list(feedback_list))

    @cherrypy.expose
    def submit_feedback(self, name, message):
        feedback_system.add_feedback(name, message)
        raise cherrypy.HTTPRedirect(REDIRECT_URL)


# ---------------------------------------------------------------------------
# Configuration / entry point
# ---------------------------------------------------------------------------

def build_app_config():
    return {
        MOUNT_PATH: {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        },
        STATIC_URL: {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': STATIC_DIR,
        },
    }


def build_server_config():
    return {
        'server.socket_host': SERVER_HOST,
        'server.socket_port': SERVER_PORT,
    }


def main():
    conf = build_app_config()
    cherrypy.config.update(build_server_config())
    cherrypy.quickstart(Root(), MOUNT_PATH, conf)


if __name__ == '__main__':
    main()
