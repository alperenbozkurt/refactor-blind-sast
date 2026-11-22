"""Tornado web service providing user registration, login and profile lookup."""

import hashlib
import json
import sqlite3

import tornado.ioloop
import tornado.web


class Database:
    """Wrapper around the SQLite user database."""

    def __init__(self):
        self.conn = sqlite3.connect('user_auth.db')
        self.init_db()

    def init_db(self):
        """Create the users table and seed the default users if it is empty."""
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
            test_users = [
                ('admin', self.hash_password('admin123'), 'admin@example.com', 1),
                ('user1', self.hash_password('password1'), 'user1@example.com', 0),
            ]
            cursor.executemany(
                'INSERT INTO users (username, password, email, is_admin) '
                'VALUES (?, ?, ?, ?)',
                test_users,
            )
            self.conn.commit()

    def hash_password(self, password):
        """Return the SHA-256 hex digest of the given password."""
        return hashlib.sha256(password.encode()).hexdigest()


class BaseHandler(tornado.web.RequestHandler):
    """Base handler that always responds with JSON."""

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def write_error(self, status_code, **kwargs):
        self.write(json.dumps({
            'error': self._reason,
            'status_code': status_code,
        }))


class RegisterHandler(BaseHandler):
    """Create a new user account."""

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
            self.write(json.dumps({'status': 'success'}))
        except sqlite3.IntegrityError:
            raise tornado.web.HTTPError(400, 'Username already exists')


class LoginHandler(BaseHandler):
    """Authenticate a user and return their id and admin flag."""

    def post(self):
        try:
            data = json.loads(self.request.body)
            username = data['username']
            password = data['password']

            db = Database()
            cursor = db.conn.cursor()
            cursor.execute(
                'SELECT id, password, is_admin FROM users WHERE username = ?',
                (username,),
            )
            user = cursor.fetchone()
            if user and user[1] == db.hash_password(password):
                self.write(json.dumps({
                    'status': 'success',
                    'user_id': user[0],
                    'is_admin': bool(user[2]),
                }))
            else:
                raise tornado.web.HTTPError(401, 'Invalid credentials')
        except Exception as e:
            # Any failure, including the 401 raised above, is reported as 400.
            raise tornado.web.HTTPError(400, str(e))


class UserProfileHandler(BaseHandler):
    """Return the public profile of the user with the given id."""

    def get(self, user_id):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(
            'SELECT id, username, email FROM users WHERE id = ?',
            (user_id,),
        )
        user = cursor.fetchone()
        if user is None:
            raise tornado.web.HTTPError(404, 'User not found')
        self.write(json.dumps({
            'id': user[0],
            'username': user[1],
            'email': user[2],
        }))


class AdminHandler(BaseHandler):
    """List all admin users."""

    def get(self):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute('SELECT id, username, email FROM users WHERE is_admin = 1')
        admins = [
            {'id': row[0], 'username': row[1], 'email': row[2]}
            for row in cursor.fetchall()
        ]
        self.write(json.dumps(admins))


def make_app():
    """Build the Tornado application with its URL routes."""
    return tornado.web.Application([
        ('/register', RegisterHandler),
        ('/login', LoginHandler),
        ('/user/([0-9]+)', UserProfileHandler),
        ('/admin/users', AdminHandler),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
