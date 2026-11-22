import cherrypy
import sqlite3
import os
import html
from contextlib import closing
from datetime import datetime

DB_NAME = 'feedback.db'

MIN_RATING = 1
MAX_RATING = 5

SERVER_CONFIG = {
    'server.socket_host': '0.0.0.0',
    'tools.encode.on': True,
    'tools.encode.encoding': 'utf-8',
    'tools.decode.on': True,
}

CREATE_TABLE_SQL = (
    '\n                CREATE TABLE feedback (\n'
    '                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                    username TEXT,\n'
    '                    message TEXT,\n'
    '                    rating INTEGER,\n'
    '                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP\n'
    '                )\n            '
)

INSERT_FEEDBACK_SQL = (
    '\n            INSERT INTO feedback (username, message, rating)\n'
    '            VALUES (?, ?, ?)\n        '
)

SELECT_ALL_FEEDBACK_SQL = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_STYLE_BLOCK = (
    '            <style>\n'
    '                table { border-collapse: collapse; width: 100%; }\n'
    '                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n'
    '                th { background-color: #f2f2f2; }\n'
    '            </style>\n'
)


def _page_head(title):
    return (
        '\n        <html>\n'
        '        <head>\n'
        f'            <title>{title}</title>\n'
        + _STYLE_BLOCK
        + '        </head>\n'
    )


_PAGE_FOOTER = '        </body>\n        </html>\n        '

INDEX_BODY = (
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
)

INDEX_HTML = _page_head('Feedback System') + INDEX_BODY + _PAGE_FOOTER

VIEW_HEADER_HTML = (
    _page_head('Feedback Results')
    + '        <body>\n'
    '            <h1>All Feedback</h1>\n'
    '            <table>\n'
    '                <tr><th>Username</th><th>Message</th><th>Rating</th><th>Date</th></tr>\n'
    '        '
)

VIEW_ROW_TEMPLATE = (
    '\n                <tr>\n'
    '                    <td>{username}</td>\n'
    '                    <td>{message}</td>\n'
    '                    <td>{rating}/5</td>\n'
    '                    <td>{timestamp}</td>\n'
    '                </tr>\n'
    '            '
)

VIEW_FOOTER_HTML = (
    '\n            </table>\n'
    '            <p><a href="/">Submit more feedback</a></p>\n'
    '        </body>\n'
    '        </html>\n'
    '        '
)


def _render_row(item):
    return VIEW_ROW_TEMPLATE.format(
        username=html.escape(item[0]),
        message=html.escape(item[1]),
        rating=html.escape(str(item[2])),
        timestamp=html.escape(item[3]),
    )


def _render_view(feedback):
    return VIEW_HEADER_HTML + ''.join(_render_row(item) for item in feedback) + VIEW_FOOTER_HTML


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _connect():
    return closing(sqlite3.connect(DB_NAME))


def _validate_rating(rating):
    try:
        rating = int(rating)
        if rating < MIN_RATING or rating > MAX_RATING:
            raise ValueError('Rating must be between 1 and 5')
    except ValueError:
        raise ValueError('Invalid rating value')
    return rating


class FeedbackSystem:

    def __init__(self):
        self.setup_database()

    def setup_database(self):
        if not os.path.exists(DB_NAME):
            with _connect() as conn:
                cursor = conn.cursor()
                cursor.execute(CREATE_TABLE_SQL)
                conn.commit()

    def add_feedback(self, username, message, rating):
        rating = _validate_rating(rating)
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                INSERT_FEEDBACK_SQL,
                (html.escape(username), html.escape(message), rating),
            )
            conn.commit()

    def get_all_feedback(self):
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_ALL_FEEDBACK_SQL)
            feedback = cursor.fetchall()
        return feedback


feedback_system = FeedbackSystem()


# ---------------------------------------------------------------------------
# Web application
# ---------------------------------------------------------------------------

class FeedbackApp:

    @cherrypy.expose
    def index(self):
        return INDEX_HTML

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
        return _render_view(feedback)


def main():
    cherrypy.config.update(SERVER_CONFIG)
    cherrypy.quickstart(FeedbackApp())


if __name__ == '__main__':
    main()
