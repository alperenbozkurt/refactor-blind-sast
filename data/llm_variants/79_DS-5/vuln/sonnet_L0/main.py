import os
import sqlite3

import cherrypy

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

INSERT_FEEDBACK_SQL = '''
            INSERT INTO feedback (username, message, rating)
            VALUES (?, ?, ?)
        '''

SELECT_ALL_FEEDBACK_SQL = (
    'SELECT username, message, rating, timestamp '
    'FROM feedback ORDER BY timestamp DESC'
)

INDEX_HTML = '''
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
    "<h1>All Feedback</h1><table border='1'><tr><th>Username</th>"
    "<th>Message</th><th>Rating</th><th>Date</th></tr>"
)


class FeedbackSystem:

    def __init__(self):
        self.setup_database()

    def setup_database(self):
        if os.path.exists(DB_NAME):
            return
        conn = sqlite3.connect(DB_NAME)
        try:
            conn.cursor().execute(CREATE_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    def add_feedback(self, username, message, rating):
        conn = sqlite3.connect(DB_NAME)
        try:
            conn.cursor().execute(INSERT_FEEDBACK_SQL, (username, message, rating))
            conn.commit()
        finally:
            conn.close()

    def get_all_feedback(self):
        conn = sqlite3.connect(DB_NAME)
        try:
            cursor = conn.cursor()
            cursor.execute(SELECT_ALL_FEEDBACK_SQL)
            return cursor.fetchall()
        finally:
            conn.close()


feedback_system = FeedbackSystem()


def _render_feedback(feedback):
    rows = ''.join(
        f'<tr><td>{item[0]}</td><td>{item[1]}</td>'
        f'<td>{item[2]}/5</td><td>{item[3]}</td></tr>'
        for item in feedback
    )
    return FEEDBACK_TABLE_HEADER + rows + '</table>'


class FeedbackApp:

    @cherrypy.expose
    def index(self):
        return INDEX_HTML

    @cherrypy.expose
    def submit(self, username, message, rating):
        feedback_system.add_feedback(username, message, rating)
        raise cherrypy.HTTPRedirect('/view')

    @cherrypy.expose
    def view(self):
        feedback = feedback_system.get_all_feedback()
        return _render_feedback(feedback)


if __name__ == '__main__':
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.quickstart(FeedbackApp())
