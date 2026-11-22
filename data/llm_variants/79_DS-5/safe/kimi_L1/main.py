import contextlib
import html
import os
import sqlite3
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

_SELECT_ALL_FEEDBACK_SQL = 'SELECT username, message, rating, timestamp FROM feedback ORDER BY timestamp DESC'

_INDEX_PAGE = '''
        <html>
        <head>
            <title>Feedback System</title>
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
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

_VIEW_PAGE_HEADER = '''
        <html>
        <head>
            <title>Feedback Results</title>
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <h1>All Feedback</h1>
            <table>
                <tr><th>Username</th><th>Message</th><th>Rating</th><th>Date</th></tr>
        '''

_FEEDBACK_ROW_TEMPLATE = (
    '\n                <tr>\n'
    '                    <td>{username}</td>\n'
    '                    <td>{message}</td>\n'
    '                    <td>{rating}/5</td>\n'
    '                    <td>{timestamp}</td>\n'
    '                </tr>\n'
    '            '
)

_VIEW_PAGE_FOOTER = '''
            </table>
            <p><a href="/">Submit more feedback</a></p>
        </body>
        </html>
        '''


class FeedbackSystem:
    """Persist and retrieve user feedback in a SQLite database."""

    def __init__(self):
        self.setup_database()

    @staticmethod
    def _connect():
        return sqlite3.connect(DB_NAME)

    def setup_database(self):
        """Create the feedback table unless the database already exists."""
        if os.path.exists(DB_NAME):
            return
        with contextlib.closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(_CREATE_TABLE_SQL)
            conn.commit()

    def add_feedback(self, username, message, rating):
        """Validate the rating and store a single feedback entry."""
        rating = self._validate_rating(rating)
        with contextlib.closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                _INSERT_FEEDBACK_SQL,
                (html.escape(username), html.escape(message), rating),
            )
            conn.commit()

    @staticmethod
    def _validate_rating(rating):
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError('Rating must be between 1 and 5')
        except ValueError:
            raise ValueError('Invalid rating value')
        return rating

    def get_all_feedback(self):
        """Return all feedback entries, most recent first."""
        with contextlib.closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(_SELECT_ALL_FEEDBACK_SQL)
            return cursor.fetchall()


feedback_system = FeedbackSystem()


class FeedbackApp:
    """CherryPy handlers for the feedback web interface."""

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
        rows = [
            _FEEDBACK_ROW_TEMPLATE.format(
                username=html.escape(item[0]),
                message=html.escape(item[1]),
                rating=html.escape(str(item[2])),
                timestamp=html.escape(item[3]),
            )
            for item in feedback_system.get_all_feedback()
        ]
        return _VIEW_PAGE_HEADER + ''.join(rows) + _VIEW_PAGE_FOOTER


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True,
    })
    cherrypy.quickstart(FeedbackApp())
