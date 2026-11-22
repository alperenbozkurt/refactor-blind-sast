"""Customer feedback web application (CherryPy + SQLite).

Layout: configuration constants, SQL statements, HTML templates, small
helper functions, then the two public classes -- ``FeedbackSystem`` for
persistence and ``FeedbackApp`` for the web interface.
"""

import cherrypy
import sqlite3
import os
import html
from contextlib import contextmanager
from datetime import datetime

DB_NAME = 'feedback.db'

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_MIN_RATING = 1
_MAX_RATING = 5

_MSG_FIELDS_REQUIRED = 'All fields are required'
_MSG_RATING_OUT_OF_RANGE = 'Rating must be between 1 and 5'
_MSG_RATING_INVALID = 'Invalid rating value'

_CHERRYPY_CONFIG = {
    'server.socket_host': '0.0.0.0',
    'tools.encode.on': True,
    'tools.encode.encoding': 'utf-8',
    'tools.decode.on': True,
}

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

_SQL_CREATE_FEEDBACK_TABLE = """
                CREATE TABLE feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    message TEXT,
                    rating INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """

_SQL_INSERT_FEEDBACK = """
            INSERT INTO feedback (username, message, rating)
            VALUES (?, ?, ?)
        """

_SQL_SELECT_ALL_FEEDBACK = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_TABLE_STYLES = (
    '\n                table { border-collapse: collapse; width: 100%; }\n'
    '                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n'
    '                th { background-color: #f2f2f2; }\n            '
)

_INDEX_PAGE = f"""
        <html>
        <head>
            <title>Feedback System</title>
            <style>{_TABLE_STYLES}</style>
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
        """

_VIEW_PAGE_HEADER = f"""
        <html>
        <head>
            <title>Feedback Results</title>
            <style>{_TABLE_STYLES}</style>
        </head>
        <body>
            <h1>All Feedback</h1>
            <table>
                <tr><th>Username</th><th>Message</th><th>Rating</th><th>Date</th></tr>
        """

_VIEW_PAGE_FOOTER = """
            </table>
            <p><a href="/">Submit more feedback</a></p>
        </body>
        </html>
        """

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

@contextmanager
def _db_connection():
    """Yield a SQLite connection to the feedback database, closing it on exit."""
    connection = sqlite3.connect(DB_NAME)
    try:
        yield connection
    finally:
        connection.close()


def _parse_rating(rating):
    """Validate *rating* and return it as an int within the allowed range."""
    try:
        rating = int(rating)
        if rating < _MIN_RATING or rating > _MAX_RATING:
            raise ValueError(_MSG_RATING_OUT_OF_RANGE)
    except ValueError:
        raise ValueError(_MSG_RATING_INVALID)
    return rating


def _render_feedback_row(item):
    """Render one ``(username, message, rating, timestamp)`` record as a table row."""
    username, message, rating, timestamp = item
    return f"""
                <tr>
                    <td>{html.escape(username)}</td>
                    <td>{html.escape(message)}</td>
                    <td>{html.escape(str(rating))}/5</td>
                    <td>{html.escape(timestamp)}</td>
                </tr>
            """

# ---------------------------------------------------------------------------
# Persistence layer
# ---------------------------------------------------------------------------

class FeedbackSystem:

    def __init__(self):
        self.setup_database()

    def setup_database(self):
        if not os.path.exists(DB_NAME):
            with _db_connection() as connection:
                connection.execute(_SQL_CREATE_FEEDBACK_TABLE)
                connection.commit()

    def add_feedback(self, username, message, rating):
        rating = _parse_rating(rating)
        with _db_connection() as connection:
            connection.execute(
                _SQL_INSERT_FEEDBACK,
                (html.escape(username), html.escape(message), rating),
            )
            connection.commit()

    def get_all_feedback(self):
        with _db_connection() as connection:
            cursor = connection.execute(_SQL_SELECT_ALL_FEEDBACK)
            return cursor.fetchall()


feedback_system = FeedbackSystem()

# ---------------------------------------------------------------------------
# Web interface
# ---------------------------------------------------------------------------

class FeedbackApp:

    @cherrypy.expose
    def index(self):
        return _INDEX_PAGE

    @cherrypy.expose
    def submit(self, username=None, message=None, rating=None):
        if not all([username, message, rating]):
            raise cherrypy.HTTPError(400, _MSG_FIELDS_REQUIRED)
        try:
            feedback_system.add_feedback(username, message, rating)
        except ValueError as e:
            raise cherrypy.HTTPError(400, str(e))
        raise cherrypy.HTTPRedirect('/view')

    @cherrypy.expose
    def view(self):
        feedback = feedback_system.get_all_feedback()
        rows = ''.join(_render_feedback_row(item) for item in feedback)
        return _VIEW_PAGE_HEADER + rows + _VIEW_PAGE_FOOTER


if __name__ == '__main__':
    cherrypy.config.update(_CHERRYPY_CONFIG)
    cherrypy.quickstart(FeedbackApp())
