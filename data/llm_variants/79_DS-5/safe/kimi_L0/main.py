import html
import os
import sqlite3
from contextlib import closing
from datetime import datetime

import cherrypy

DB_NAME = 'feedback.db'

_CREATE_TABLE_SQL = '''
    CREATE TABLE feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        rating INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
'''

_INSERT_FEEDBACK_SQL = '''
    INSERT INTO feedback (username, message, rating)
    VALUES (?, ?, ?)
'''

_SELECT_ALL_FEEDBACK_SQL = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)

_TABLE_STYLE_BLOCK = '''
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>'''

_INDEX_PAGE = f'''
        <html>
        <head>
            <title>Feedback System</title>{_TABLE_STYLE_BLOCK}
        </head>
        <body>
            <h1>Submit Feedback</h1>
            <form method="post" action="/submit">
                <label>Name: <input type="text" name="username" required></label><br>
                <label>Message: <textarea name="message" required></textarea></label><br>
                <label>Rating: 
                    <select name="rating" required>
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

_VIEW_PAGE_HEADER = f'''
        <html>
        <head>
            <title>Feedback Results</title>{_TABLE_STYLE_BLOCK}
        </head>
        <body>
            <h1>All Feedback</h1>
            <table>
                <tr><th>Username</th><th>Message</th><th>Rating</th><th>Date</th></tr>
        '''

_VIEW_PAGE_FOOTER = '''
            </table>
            <p><a href="/">Submit more feedback</a></p>
        </body>
        </html>
        '''


def _render_feedback_row(username, message, rating, timestamp):
    return f'''
                <tr>
                    <td>{html.escape(username)}</td>
                    <td>{html.escape(message)}</td>
                    <td>{html.escape(str(rating))}/5</td>
                    <td>{html.escape(timestamp)}</td>
                </tr>
            '''


class FeedbackSystem:
    """SQLite-backed storage for user feedback."""

    def __init__(self):
        self.setup_database()

    def setup_database(self):
        if os.path.exists(DB_NAME):
            return
        with closing(sqlite3.connect(DB_NAME)) as conn:
            with conn:
                conn.execute(_CREATE_TABLE_SQL)

    def add_feedback(self, username, message, rating):
        try:
            rating = int(rating)
        except ValueError:
            raise ValueError('Invalid rating value')
        if not 1 <= rating <= 5:
            raise ValueError('Invalid rating value')
        with closing(sqlite3.connect(DB_NAME)) as conn:
            with conn:
                conn.execute(
                    _INSERT_FEEDBACK_SQL,
                    (html.escape(username), html.escape(message), rating),
                )

    def get_all_feedback(self):
        with closing(sqlite3.connect(DB_NAME)) as conn:
            return conn.execute(_SELECT_ALL_FEEDBACK_SQL).fetchall()


feedback_system = FeedbackSystem()


class FeedbackApp:
    """CherryPy handlers for submitting and viewing feedback."""

    @cherrypy.expose
    def index(self):
        return _INDEX_PAGE

    @cherrypy.expose
    def submit(self, username=None, message=None, rating=None):
        if not all([username, message, rating]):
            raise cherrypy.HTTPError(400, 'All fields are required')
        try:
            feedback_system.add_feedback(username, message, rating)
        except ValueError as e:
            raise cherrypy.HTTPError(400, str(e))
        raise cherrypy.HTTPRedirect('/view')

    @cherrypy.expose
    def view(self):
        rows = ''.join(
            _render_feedback_row(username, message, rating, timestamp)
            for username, message, rating, timestamp in feedback_system.get_all_feedback()
        )
        return _VIEW_PAGE_HEADER + rows + _VIEW_PAGE_FOOTER


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True,
    })
    cherrypy.quickstart(FeedbackApp())
