import os
import sqlite3
from contextlib import closing

import cherrypy

DB_NAME = 'feedback.db'

SERVER_CONFIG = {'server.socket_host': '0.0.0.0'}
REDIRECT_AFTER_SUBMIT = '/view'

CREATE_TABLE_SQL = (
    '\n'
    '                CREATE TABLE feedback (\n'
    '                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                    username TEXT,\n'
    '                    message TEXT,\n'
    '                    rating INTEGER,\n'
    '                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP\n'
    '                )\n'
    '            '
)

INSERT_FEEDBACK_SQL = (
    '\n'
    '            INSERT INTO feedback (username, message, rating)\n'
    '            VALUES (?, ?, ?)\n'
    '        '
)

SELECT_ALL_FEEDBACK_SQL = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)

INDEX_HTML = (
    '\n'
    '        <html>\n'
    '        <head><title>Feedback System</title></head>\n'
    '        <body>\n'
    '            <h1>Submit Feedback</h1>\n'
    '            <form method="post" action="/submit">\n'
    '                <label>Name: <input type="text" name="username"></label><br>\n'
    '                <label>Message: <textarea name="message"></textarea></label><br>\n'
    '                <label>Rating: \n'
    '                    <select name="rating">\n'
    '                        <option value="5">5 - Excellent</option>\n'
    '                        <option value="4">4 - Good</option>\n'
    '                        <option value="3">3 - Average</option>\n'
    '                        <option value="2">2 - Poor</option>\n'
    '                        <option value="1">1 - Terrible</option>\n'
    '                    </select>\n'
    '                </label><br>\n'
    '                <button type="submit">Submit</button>\n'
    '            </form>\n'
    '            <p><a href="/view">View all feedback</a></p>\n'
    '        </body>\n'
    '        </html>\n'
    '        '
)

FEEDBACK_TABLE_HEADER = (
    "<h1>All Feedback</h1><table border='1'><tr><th>Username</th>"
    "<th>Message</th><th>Rating</th><th>Date</th></tr>"
)
FEEDBACK_TABLE_FOOTER = '</table>'


def _connect():
    """Open a new connection to the feedback database."""
    return sqlite3.connect(DB_NAME)


def _render_feedback_row(item):
    return (
        f'<tr><td>{item[0]}</td><td>{item[1]}</td>'
        f'<td>{item[2]}/5</td><td>{item[3]}</td></tr>'
    )


def _render_feedback(feedback):
    rows = ''.join(_render_feedback_row(item) for item in feedback)
    return FEEDBACK_TABLE_HEADER + rows + FEEDBACK_TABLE_FOOTER


class FeedbackSystem:

    def __init__(self):
        self.setup_database()

    def setup_database(self):
        if not os.path.exists(DB_NAME):
            with closing(_connect()) as conn:
                cursor = conn.cursor()
                cursor.execute(CREATE_TABLE_SQL)
                conn.commit()

    def add_feedback(self, username, message, rating):
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(INSERT_FEEDBACK_SQL, (username, message, rating))
            conn.commit()

    def get_all_feedback(self):
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_ALL_FEEDBACK_SQL)
            feedback = cursor.fetchall()
        return feedback


feedback_system = FeedbackSystem()


class FeedbackApp:

    @cherrypy.expose
    def index(self):
        return INDEX_HTML

    @cherrypy.expose
    def submit(self, username, message, rating):
        feedback_system.add_feedback(username, message, rating)
        raise cherrypy.HTTPRedirect(REDIRECT_AFTER_SUBMIT)

    @cherrypy.expose
    def view(self):
        feedback = feedback_system.get_all_feedback()
        return _render_feedback(feedback)


if __name__ == '__main__':
    cherrypy.config.update(SERVER_CONFIG)
    cherrypy.quickstart(FeedbackApp())
