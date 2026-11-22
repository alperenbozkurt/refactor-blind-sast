import cherrypy
import os
import sqlite3
import html
from datetime import datetime

DB_PATH = 'feedback.db'

CREATE_TABLE_SQL = (
    '\n            CREATE TABLE IF NOT EXISTS feedback (\n'
    '                id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                name TEXT NOT NULL,\n'
    '                message TEXT NOT NULL,\n'
    '                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP\n'
    '            )\n        '
)

INSERT_FEEDBACK_SQL = (
    '\n            INSERT INTO feedback (name, message) VALUES (?, ?)\n        '
)

SELECT_ALL_FEEDBACK_SQL = 'SELECT * FROM feedback ORDER BY timestamp DESC'

FEEDBACK_ITEM_TEMPLATE = (
    '\n                <div class="feedback-item">\n'
    '                    <h3>{name}</h3>\n'
    '                    <p>{message}</p>\n'
    '                    <small>{timestamp}</small>\n'
    '                </div>\n            '
)

PAGE_TEMPLATE = (
    '\n            <!DOCTYPE html>\n'
    '            <html>\n'
    '            <head>\n'
    '                <title>Feedback System</title>\n'
    '                <style>\n'
    '                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n'
    '                    .feedback-item { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; }\n'
    '                    textarea { width: 100%; height: 100px; }\n'
    '                </style>\n'
    '            </head>\n'
    '            <body>\n'
    '                <h1>Customer Feedback</h1>\n'
    '                \n'
    '                <form method="post" action="/submit_feedback">\n'
    '                    <h2>Submit Your Feedback</h2>\n'
    '                    <p>\n'
    '                        <label>Your Name:</label><br>\n'
    '                        <input type="text" name="name" required>\n'
    '                    </p>\n'
    '                    <p>\n'
    '                        <label>Your Feedback:</label><br>\n'
    '                        <textarea name="message" required></textarea>\n'
    '                    </p>\n'
    '                    <button type="submit">Submit Feedback</button>\n'
    '                </form>\n'
    '                \n'
    '                <h2>Recent Feedback</h2>\n'
    '                '
)

PAGE_SUFFIX = '\n            </body>\n            </html>\n        '


class FeedbackSystem:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
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


def _render_feedback_item(item):
    # Note: the message is intentionally inserted as-is (not escaped) to
    # preserve the original output exactly.
    return FEEDBACK_ITEM_TEMPLATE.format(
        name=html.escape(item[1]),
        message=item[2],
        timestamp=item[3],
    )


class Root:

    @cherrypy.expose
    def index(self):
        feedback_list = feedback_system.get_all_feedback()
        feedback_html = ''.join(_render_feedback_item(item) for item in feedback_list)
        return PAGE_TEMPLATE + feedback_html + PAGE_SUFFIX

    @cherrypy.expose
    def submit_feedback(self, name, message):
        feedback_system.add_feedback(name, message)
        raise cherrypy.HTTPRedirect('/')


if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './public',
        },
    }
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': 8080})
    cherrypy.quickstart(Root(), '/', conf)
