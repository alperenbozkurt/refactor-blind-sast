"""JSON user-authentication API built on Tornado and SQLite."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass

import tornado.ioloop
import tornado.web

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    """Application-wide configuration values."""

    database_name: str = 'user_auth.db'
    port: int = 8888


SETTINGS = Settings()

JSON_CONTENT_TYPE = 'application/json'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        is_admin BOOLEAN DEFAULT 0
    )
'''

COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'

INSERT_USER_SQL = (
    'INSERT INTO users (username, password, email) VALUES (?, ?, ?)'
)

INSERT_SEED_USER_SQL = (
    'INSERT INTO users (username, password, email, is_admin) '
    'VALUES (?, ?, ?, ?)'
)

SELECT_USER_BY_USERNAME_SQL = (
    'SELECT id, password, is_admin FROM users WHERE username = ?'
)

SELECT_USER_BY_ID_SQL = (
    'SELECT id, username, email FROM users WHERE id = ?'
)

SELECT_ADMINS_SQL = (
    'SELECT id, username, email FROM users WHERE is_admin = 1'
)

# ---------------------------------------------------------------------------
# Seed data and response messages
# ---------------------------------------------------------------------------

SEED_USERS = (
    ('admin', 'admin123', 'admin@example.com', 1),
    ('user1', 'password1', 'user1@example.com', 0),
)

STATUS_SUCCESS = 'success'

ERROR_USERNAME_EXISTS = 'Username already exists'
ERROR_INVALID_CREDENTIALS = 'Invalid credentials'
ERROR_USER_NOT_FOUND = 'User not found'


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def hash_password(password):
    """Return the SHA-256 hex digest used to store ``password``."""
    return hashlib.sha256(password.encode()).hexdigest()


def user_to_dict(row):
    """Convert an ``(id, username, email)`` row into a JSON-friendly dict."""
    return {'id': row[0], 'username': row[1], 'email': row[2]}


# ---------------------------------------------------------------------------
# Persistence layer
# ---------------------------------------------------------------------------


class Database:
    """Thin wrapper around the SQLite connection used by the handlers."""

    def __init__(self):
        self.conn = sqlite3.connect(SETTINGS.database_name)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(COUNT_USERS_SQL)
        if cursor.fetchone()[0] == 0:
            self._seed_users(cursor)
            self.conn.commit()

    def hash_password(self, password):
        return hash_password(password)

    def create_user(self, username, password, email):
        cursor = self.conn.cursor()
        cursor.execute(
            INSERT_USER_SQL, (username, self.hash_password(password), email)
        )
        self.conn.commit()

    def find_user_by_username(self, username):
        cursor = self.conn.cursor()
        cursor.execute(SELECT_USER_BY_USERNAME_SQL, (username,))
        return cursor.fetchone()

    def find_user_by_id(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute(SELECT_USER_BY_ID_SQL, (user_id,))
        return cursor.fetchone()

    def find_admins(self):
        cursor = self.conn.cursor()
        cursor.execute(SELECT_ADMINS_SQL)
        return cursor.fetchall()

    def _seed_users(self, cursor):
        test_users = [
            (username, self.hash_password(password), email, is_admin)
            for username, password, email, is_admin in SEED_USERS
        ]
        cursor.executemany(INSERT_SEED_USER_SQL, test_users)


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------


class BaseHandler(tornado.web.RequestHandler):

    def set_default_headers(self):
        self.set_header('Content-Type', JSON_CONTENT_TYPE)

    def write_error(self, status_code, **kwargs):
        self.write_json({'error': self._reason, 'status_code': status_code})

    def get_json_body(self):
        """Parse the request body as JSON."""
        return json.loads(self.request.body)

    def write_json(self, payload):
        """Serialise ``payload`` and write it to the response."""
        self.write(json.dumps(payload))


class RegisterHandler(BaseHandler):

    def post(self):
        try:
            data = self.get_json_body()
            username = data['username']
            password = data['password']
            email = data.get('email', '')
            db = Database()
            db.create_user(username, password, email)
            self.write_json({'status': STATUS_SUCCESS})
        except sqlite3.IntegrityError:
            raise tornado.web.HTTPError(400, ERROR_USERNAME_EXISTS)


class LoginHandler(BaseHandler):

    def post(self):
        try:
            data = self.get_json_body()
            username = data['username']
            password = data['password']
            db = Database()
            user = db.find_user_by_username(username)
            if user and user[1] == db.hash_password(password):
                self.write_json({
                    'status': STATUS_SUCCESS,
                    'user_id': user[0],
                    'is_admin': bool(user[2]),
                })
            else:
                raise tornado.web.HTTPError(401, ERROR_INVALID_CREDENTIALS)
        except Exception as e:
            raise tornado.web.HTTPError(400, str(e))


class UserProfileHandler(BaseHandler):

    def get(self, user_id):
        db = Database()
        user = db.find_user_by_id(user_id)
        if user:
            self.write_json(user_to_dict(user))
        else:
            raise tornado.web.HTTPError(404, ERROR_USER_NOT_FOUND)


class AdminHandler(BaseHandler):

    def get(self):
        db = Database()
        admins = [user_to_dict(row) for row in db.find_admins()]
        self.write_json(admins)


# ---------------------------------------------------------------------------
# Application assembly
# ---------------------------------------------------------------------------

ROUTES = [
    (r'/register', RegisterHandler),
    (r'/login', LoginHandler),
    (r'/user/([0-9]+)', UserProfileHandler),
    (r'/admin/users', AdminHandler),
]


def make_app():
    return tornado.web.Application(ROUTES)


def main():
    app = make_app()
    app.listen(SETTINGS.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
