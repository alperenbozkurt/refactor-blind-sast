"""Feedback collection web application built with CherryPy and SQLite."""

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass

import cherrypy

DB_NAME = 'feedback.db'

CREATE_FEEDBACK_TABLE_SQL = '''
                CREATE TABLE feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    message TEXT,
                    rating INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            '''

INSERT_FEEDBACK_SQL = '''
            INSERT INTO feedback (username, message, rating)
            VALUES (?, ?, ?)
        '''

SELECT_ALL_FEEDBACK_SQL = (
    'SELECT username, message, rating, timestamp FROM feedback '
    'ORDER BY timestamp DESC'
)

INDEX_PAGE_HTML = '''
        <html>
        <head><title>Feedback System</title></head>
        <body>
            <h1>Submit Feedback</h1>
            <form method="post" action="/submit">
                <label>Name: <input type="text" name="username"></label><br>
                <label>Message: <textarea name="message"></textarea></label><br>
                <label>Rating: 
                    <select name="rating">
                        <option value="5">5 - Excellent</option>
                        <option value="4">4 - Good</option>
                        <option value="3">3 - Average</option>
                        <option value="2">2 - Poor</option>
                        <option value="1">1 - Terrible</option>
                    </select>
                </label><br>
                <button type="submit">Submit</button>
            </form>
            <p><a href="/view">View all feedback</a></p>
        </body>
        </html>
        '''

FEEDBACK_TABLE_HEADER = (
    "<h1>All Feedback</h1>"
    "<table border='1'>"
    '<tr><th>Username</th><th>Message</th><th>Rating</th><th>Date</th></tr>'
)
FEEDBACK_ROW_TEMPLATE = '<tr><td>{}</td><td>{}</td><td>{}/5</td><td>{}</td></tr>'
FEEDBACK_TABLE_FOOTER = '</table>'

VIEW_PAGE_URL = '/view'


@dataclass(frozen=True)
class ServerConfig:
    """Settings used to configure the CherryPy server."""

    socket_host: str = '0.0.0.0'

    def to_cherrypy_config(self):
        return {'server.socket_host': self.socket_host}


def _connect():
    """Return a new connection to the feedback database."""
    return sqlite3.connect(DB_NAME)


def render_feedback(feedback):
    """Build the HTML table displaying all feedback entries."""
    rows = ''.join(FEEDBACK_ROW_TEMPLATE.format(*item) for item in feedback)
    return FEEDBACK_TABLE_HEADER + rows + FEEDBACK_TABLE_FOOTER


class FeedbackSystem:
    """SQLite-backed storage for user feedback."""

    def __init__(self):
        self.db_name = DB_NAME
        self.setup_database()

    def setup_database(self):
        if not os.path.exists(self.db_name):
            with closing(_connect()) as conn:
                conn.execute(CREATE_FEEDBACK_TABLE_SQL)
                conn.commit()

    def add_feedback(self, username, message, rating):
        with closing(_connect()) as conn:
            conn.execute(INSERT_FEEDBACK_SQL, (username, message, rating))
            conn.commit()

    def get_all_feedback(self):
        with closing(_connect()) as conn:
            cursor = conn.execute(SELECT_ALL_FEEDBACK_SQL)
            return cursor.fetchall()


feedback_system = FeedbackSystem()


class FeedbackApp:
    """CherryPy application exposing the feedback pages."""

    @cherrypy.expose
    def index(self):
        return INDEX_PAGE_HTML

    @cherrypy.expose
    def submit(self, username, message, rating):
        feedback_system.add_feedback(username, message, rating)
        raise cherrypy.HTTPRedirect(VIEW_PAGE_URL)

    @cherrypy.expose
    def view(self):
        feedback = feedback_system.get_all_feedback()
        return render_feedback(feedback)


def main():
    cherrypy.config.update(ServerConfig().to_cherrypy_config())
    cherrypy.quickstart(FeedbackApp())


if __name__ == '__main__':
    main()
