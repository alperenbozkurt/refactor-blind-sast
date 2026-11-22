import cherrypy
import sqlite3
import os
import html
from datetime import datetime

DB_NAME = 'feedback.db'

CREATE_TABLE_SQL = '''
    CREATE TABLE feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        rating INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
'''

INSERT_SQL = '''
    INSERT INTO feedback (username, message, rating)
    VALUES (?, ?, ?)
'''

SELECT_ALL_SQL = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)


class FeedbackSystem:

    def __init__(self):
        self.setup_database()

    @staticmethod
    def _connect():
        return sqlite3.connect(DB_NAME)

    def setup_database(self):
        if os.path.exists(DB_NAME):
            return
        conn = self._connect()
        conn.cursor().execute(CREATE_TABLE_SQL)
        conn.commit()
        conn.close()

    @staticmethod
    def _validate_rating(rating):
        try:
            rating = int(rating)
        except ValueError:
            raise ValueError('Invalid rating value')
        if rating < 1 or rating > 5:
            raise ValueError('Invalid rating value')
        return rating

    def add_feedback(self, username, message, rating):
        rating = self._validate_rating(rating)
        conn = self._connect()
        conn.cursor().execute(
            INSERT_SQL,
            (html.escape(username), html.escape(message), rating),
        )
        conn.commit()
        conn.close()

    def get_all_feedback(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_SQL)
        feedback = cursor.fetchall()
        conn.close()
        return feedback


feedback_system = FeedbackSystem()


_STYLE_BLOCK = """            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
"""


def _page_head(title):
    return (
        '\n        <html>\n'
        '        <head>\n'
        f'            <title>{title}</title>\n'
        + _STYLE_BLOCK +
        '        </head>\n'
        '        <body>\n'
    )


INDEX_HTML = (
    _page_head('Feedback System')
    + """            <h1>Submit Feedback</h1>
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
)

VIEW_HEADER_HTML = (
    _page_head('Feedback Results')
    + '            <h1>All Feedback</h1>\n'
    '            <table>\n'
    '                <tr><th>Username</th><th>Message</th>'
    '<th>Rating</th><th>Date</th></tr>\n'
    '        '
)

VIEW_FOOTER_HTML = (
    '\n            </table>\n'
    '            <p><a href="/">Submit more feedback</a></p>\n'
    '        </body>\n'
    '        </html>\n'
    '        '
)


def _render_row(item):
    return (
        '\n                <tr>\n'
        f'                    <td>{html.escape(item[0])}</td>\n'
        f'                    <td>{html.escape(item[1])}</td>\n'
        f'                    <td>{html.escape(str(item[2]))}/5</td>\n'
        f'                    <td>{html.escape(item[3])}</td>\n'
        '                </tr>\n'
        '            '
    )


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
        rows = ''.join(_render_row(item) for item in feedback)
        return VIEW_HEADER_HTML + rows + VIEW_FOOTER_HTML


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True,
    })
    cherrypy.quickstart(FeedbackApp())
