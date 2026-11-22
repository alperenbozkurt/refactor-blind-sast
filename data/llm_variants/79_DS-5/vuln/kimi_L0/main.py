import os
import sqlite3
from contextlib import closing

import cherrypy

DB_NAME = 'feedback.db'

_CREATE_TABLE_SQL = """
    CREATE TABLE feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        rating INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
"""

_ADD_FEEDBACK_SQL = """
    INSERT INTO feedback (username, message, rating)
    VALUES (?, ?, ?)
"""

_GET_ALL_FEEDBACK_SQL = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)

_INDEX_HTML = '''
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

_FEEDBACK_TABLE_HEADER = (
    "<h1>All Feedback</h1>"
    "<table border='1'>"
    "<tr><th>Username</th><th>Message</th><th>Rating</th><th>Date</th></tr>"
)


class FeedbackSystem:
    """Handles persistence of user feedback in a SQLite database."""

    def __init__(self):
        self.setup_database()

    def setup_database(self):
        """Create the feedback table if the database does not exist yet."""
        if os.path.exists(DB_NAME):
            return
        with closing(sqlite3.connect(DB_NAME)) as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()

    def add_feedback(self, username, message, rating):
        """Insert a single feedback entry into the database."""
        with closing(sqlite3.connect(DB_NAME)) as conn:
            conn.execute(_ADD_FEEDBACK_SQL, (username, message, rating))
            conn.commit()

    def get_all_feedback(self):
        """Return all feedback entries, newest first."""
        with closing(sqlite3.connect(DB_NAME)) as conn:
            return conn.execute(_GET_ALL_FEEDBACK_SQL).fetchall()


feedback_system = FeedbackSystem()


class FeedbackApp:
    """CherryPy request handler exposing the feedback web interface."""

    @cherrypy.expose
    def index(self):
        return _INDEX_HTML

    @cherrypy.expose
    def submit(self, username, message, rating):
        feedback_system.add_feedback(username, message, rating)
        raise cherrypy.HTTPRedirect('/view')

    @cherrypy.expose
    def view(self):
        def render_feedback(feedback):
            rows = ''.join(
                f'<tr><td>{username}</td><td>{message}</td>'
                f'<td>{rating}/5</td><td>{timestamp}</td></tr>'
                for username, message, rating, timestamp in feedback
            )
            return _FEEDBACK_TABLE_HEADER + rows + '</table>'

        feedback = feedback_system.get_all_feedback()
        return render_feedback(feedback)


if __name__ == '__main__':
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.quickstart(FeedbackApp())
