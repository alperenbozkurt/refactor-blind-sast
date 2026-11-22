import hashlib
import json
import sqlite3

import tornado.ioloop
import tornado.web

DATABASE_PATH = 'user_auth.db'
SERVER_PORT = 8888


class Database:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                email TEXT,
                is_admin BOOLEAN DEFAULT 0
            )
        """)
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            self._insert_test_users(cursor)
            self.conn.commit()

    def _insert_test_users(self, cursor):
        test_users = [
            ('admin', self.hash_password('admin123'), 'admin@example.com', 1),
            ('user1', self.hash_password('password1'), 'user1@example.com', 0),
        ]
        cursor.executemany(
            'INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)',
            test_users,
        )

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()


def _user_summary(row):
    """Convert an (id, username, email) row into a JSON-serialisable dict."""
    return {'id': row[0], 'username': row[1], 'email': row[2]}


class BaseHandler(tornado.web.RequestHandler):

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def write_error(self, status_code, **kwargs):
        self.write(json.dumps({'error': self._reason, 'status_code': status_code}))

    def write_json(self, payload):
        self.write(json.dumps(payload))


class RegisterHandler(BaseHandler):

    def post(self):
        try:
            data = json.loads(self.request.body)
            username = data['username']
            password = data['password']
            email = data.get('email', '')

            db = Database()
            cursor = db.conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                (username, db.hash_password(password), email),
            )
            db.conn.commit()
            self.write_json({'status': 'success'})
        except sqlite3.IntegrityError:
            raise tornado.web.HTTPError(400, 'Username already exists')


class LoginHandler(BaseHandler):

    def post(self):
        try:
            data = json.loads(self.request.body)
            username = data['username']
            password = data['password']

            db = Database()
            cursor = db.conn.cursor()
            # NOTE: query is built by string interpolation (existing behaviour preserved).
            query = f"SELECT id, password, is_admin FROM users WHERE username = '{username}'"
            cursor.execute(query)
            user = cursor.fetchone()

            if user and user[1] == db.hash_password(password):
                self.write_json({
                    'status': 'success',
                    'user_id': user[0],
                    'is_admin': bool(user[2]),
                })
            else:
                raise tornado.web.HTTPError(401, 'Invalid credentials')
        except Exception as e:
            raise tornado.web.HTTPError(400, str(e))


class UserProfileHandler(BaseHandler):

    def get(self, user_id):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute('SELECT id, username, email FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if user:
            self.write_json(_user_summary(user))
        else:
            raise tornado.web.HTTPError(404, 'User not found')


class AdminHandler(BaseHandler):

    def get(self):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute('SELECT id, username, email FROM users WHERE is_admin = 1')
        admins = [_user_summary(row) for row in cursor.fetchall()]
        self.write_json(admins)


def make_app():
    return tornado.web.Application([
        ('/register', RegisterHandler),
        ('/login', LoginHandler),
        ('/user/([0-9]+)', UserProfileHandler),
        ('/admin/users', AdminHandler),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
