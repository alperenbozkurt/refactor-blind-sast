import cherrypy
import os
import sqlite3
import html
from datetime import datetime

DATABASE_PATH = 'feedback.db'

CREATE_TABLE_SQL = """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """

INSERT_FEEDBACK_SQL = """
            INSERT INTO feedback (name, message) VALUES (?, ?)
        """

SELECT_ALL_FEEDBACK_SQL = 'SELECT * FROM feedback ORDER BY timestamp DESC'

FEEDBACK_ITEM_TEMPLATE = '''
                <div class="feedback-item">
                    <h3>{name}</h3>
                    <p>{message}</p>
                    <small>{timestamp}</small>
                </div>
            '''

INDEX_PAGE_TEMPLATE = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Feedback System</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .feedback-item {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; }}
                    textarea {{ width: 100%; height: 100px; }}
                </style>
            </head>
            <body>
                <h1>Customer Feedback</h1>
                
                <form method="post" action="/submit_feedback">
                    <h2>Submit Your Feedback</h2>
                    <p>
                        <label>Your Name:</label><br>
                        <input type="text" name="name" required>
                    </p>
                    <p>
                        <label>Your Feedback:</label><br>
                        <textarea name="message" required></textarea>
                    </p>
                    <button type="submit">Submit Feedback</button>
                </form>
                
                <h2>Recent Feedback</h2>
                {feedback_html}
            </body>
            </html>
        '''


class FeedbackSystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)
        self.conn.commit()

    def add_feedback(self, name, message):
        cursor = self.conn.cursor()
        cursor.execute(INSERT_FEEDBACK_SQL, (name, message))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_feedback(self):
        cursor = self.conn.cursor()
        cursor.execute(SELECT_ALL_FEEDBACK_SQL)
        return cursor.fetchall()


feedback_system = FeedbackSystem()


class Root:

    @cherrypy.expose
    def index(self):
        feedback_html = ''.join(
            FEEDBACK_ITEM_TEMPLATE.format(
                name=html.escape(item[1]),
                message=item[2],
                timestamp=item[3],
            )
            for item in feedback_system.get_all_feedback()
        )
        return INDEX_PAGE_TEMPLATE.format(feedback_html=feedback_html)

    @cherrypy.expose
    def submit_feedback(self, name, message):
        feedback_system.add_feedback(name, message)
        raise cherrypy.HTTPRedirect('/')


if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './public',
        },
    }
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080,
    })
    cherrypy.quickstart(Root(), '/', conf)
