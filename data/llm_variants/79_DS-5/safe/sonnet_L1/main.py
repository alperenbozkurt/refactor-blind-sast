import cherrypy
import sqlite3
import os
import html
from contextlib import closing
from datetime import datetime

DB_NAME = 'feedback.db'

MIN_RATING = 1
MAX_RATING = 5

CREATE_TABLE_SQL = """
    CREATE TABLE feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        rating INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
"""

INSERT_FEEDBACK_SQL = """
    INSERT INTO feedback (username, message, rating)
    VALUES (?, ?, ?)
"""

SELECT_ALL_FEEDBACK_SQL = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)

PAGE_STYLE = (
    '            <style>\n'
    '                table { border-collapse: collapse; width: 100%; }\n'
    '                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n'
    '                th { background-color: #f2f2f2; }\n'
    '            </style>\n'
)

INDEX_HEAD = (
    '\n'
    '        <html>\n'
    '        <head>\n'
    '            <title>Feedback System</title>\n'
)

INDEX_BODY = (
    '        </head>\n'
    '        <body>\n'
    '            <h1>Submit Feedback</h1>\n'
    '            <form method="post" action="/submit">\n'
    '                <label>Name: <input type="text" name="username" required></label><br>\n'
    '                <label>Message: <textarea name="message" required></textarea></label><br>\n'
    '                <label>Rating: \n'
    '                    <select name="rating" required>\n'
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

INDEX_PAGE = INDEX_HEAD + PAGE_STYLE + INDEX_BODY

VIEW_HEAD = (
    '\n'
    '        <html>\n'
    '        <head>\n'
    '            <title>Feedback Results</title>\n'
)

VIEW_BODY_START = (
    '        </head>\n'
    '        <body>\n'
    '            <h1>All Feedback</h1>\n'
    '            <table>\n'
    '                <tr><th>Username</th><th>Message</th><th>Rating</th><th>Date</th></tr>\n'
    '        '
)

VIEW_FOOTER = (
    '\n'
    '            </table>\n'
    '            <p><a href="/">Submit more feedback</a></p>\n'
    '        </body>\n'
    '        </html>\n'
    '        '
)

VIEW_PAGE_START = VIEW_HEAD + PAGE_STYLE + VIEW_BODY_START


def _parse_rating(rating):
    """Convert the rating to an int and check its range."""
    try:
        rating = int(rating)
        if rating < MIN_RATING or rating > MAX_RATING:
            raise ValueError('Rating must be between 1 and 5')
    except ValueError:
        raise ValueError('Invalid rating value')
    return rating


def _render_feedback_row(item):
    """Render a single feedback record as an HTML table row."""
    username, message, rating, timestamp = item[0], item[1], item[2], item[3]
    return (
        '\n'
        '                <tr>\n'
        f'                    <td>{html.escape(username)}</td>\n'
        f'                    <td>{html.escape(message)}</td>\n'
        f'                    <td>{html.escape(str(rating))}/5</td>\n'
        f'                    <td>{html.escape(timestamp)}</td>\n'
        '                </tr>\n'
        '            '
    )


class FeedbackSystem:

    def __init__(self):
        self.setup_database()

    def setup_database(self):
        if not os.path.exists(DB_NAME):
            with closing(sqlite3.connect(DB_NAME)) as conn:
                conn.cursor().execute(CREATE_TABLE_SQL)
                conn.commit()

    def add_feedback(self, username, message, rating):
        rating = _parse_rating(rating)
        with closing(sqlite3.connect(DB_NAME)) as conn:
            conn.cursor().execute(
                INSERT_FEEDBACK_SQL,
                (html.escape(username), html.escape(message), rating),
            )
            conn.commit()

    def get_all_feedback(self):
        with closing(sqlite3.connect(DB_NAME)) as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_ALL_FEEDBACK_SQL)
            return cursor.fetchall()


feedback_system = FeedbackSystem()


class FeedbackApp:

    @cherrypy.expose
    def index(self):
        return INDEX_PAGE

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
        feedback = feedback_system.get_all_feedback()
        rows = ''.join(_render_feedback_row(item) for item in feedback)
        return VIEW_PAGE_START + rows + VIEW_FOOTER


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True,
    })
    cherrypy.quickstart(FeedbackApp())
