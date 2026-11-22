"""User-authentication JSON API backed by SQLite and Tornado.

The public interface (module-level names, classes, methods, routes and the
command-line behaviour) is identical to the original module; the internals
have been reorganised into named constants and small helpers.
"""

import hashlib
import json
import sqlite3

import tornado.ioloop
import tornado.web

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'user_auth.db'
SERVER_PORT = 8888

CONTENT_TYPE_HEADER = 'Content-Type'
JSON_CONTENT_TYPE = 'application/json'

# ---------------------------------------------------------------------------
# SQL statements and seed data
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE_SQL = """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                email TEXT,
                is_admin BOOLEAN DEFAULT 0
            )
        """

COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'

SEED_USERS_SQL = (
    'INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)'
)

INSERT_USER_SQL = 'INSERT INTO users (username, password, email) VALUES (?, ?, ?)'

SELECT_USER_BY_ID_SQL = 'SELECT id, username, email FROM users WHERE id = ?'

SELECT_ADMINS_SQL = 'SELECT id, username, email FROM users WHERE is_admin = 1'

# Accounts inserted the first time the database is created.
DEFAULT_USERS = (
    ('admin', 'admin123', 'admin@example.com', 1),
    ('user1', 'password1', 'user1@example.com', 0),
)


def _user_profile_dict(row):
    """Build the public JSON representation of a user row."""
    return {'id': row[0], 'username': row[1], 'email': row[2]}


class Database:
    """SQLite connection wrapper that guarantees the schema exists."""

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        if self._user_count(cursor) == 0:
            self._seed_default_users(cursor)

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def _user_count(self, cursor):
        cursor.execute(COUNT_USERS_SQL)
        return cursor.fetchone()[0]

    def _seed_default_users(self, cursor):
        test_users = [
            (username, self.hash_password(password), email, is_admin)
            for username, password, email, is_admin in DEFAULT_USERS
        ]
        cursor.executemany(SEED_USERS_SQL, test_users)
        self.conn.commit()


class BaseHandler(tornado.web.RequestHandler):
    """Common JSON request/response handling for all API handlers."""

    def set_default_headers(self):
        self.set_header(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE)

    def write_error(self, status_code, **kwargs):
        self.write_json({'error': self._reason, 'status_code': status_code})

    def parse_json_body(self):
        """Decode the request body as JSON."""
        return json.loads(self.request.body)

    def write_json(self, payload):
        """Serialize *payload* as JSON and send it to the client."""
        self.write(json.dumps(payload))


class RegisterHandler(BaseHandler):

    def post(self):
        try:
            data = self.parse_json_body()
            username = data['username']
            password = data['password']
            email = data.get('email', '')
            self._create_user(username, password, email)
            self.write_json({'status': 'success'})
        except sqlite3.IntegrityError:
            raise tornado.web.HTTPError(400, 'Username already exists')

    def _create_user(self, username, password, email):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(
            INSERT_USER_SQL,
            (username, db.hash_password(password), email),
        )
        db.conn.commit()


class LoginHandler(BaseHandler):

    def post(self):
        try:
            data = self.parse_json_body()
            username = data['username']
            password = data['password']
            db = Database()
            user = self._find_user(db, username)
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

    def _find_user(self, db, username):
        cursor = db.conn.cursor()
        # Kept verbatim from the original implementation to preserve behaviour.
        query = f"SELECT id, password, is_admin FROM users WHERE username = '{username}'"
        cursor.execute(query)
        return cursor.fetchone()


class UserProfileHandler(BaseHandler):

    def get(self, user_id):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_USER_BY_ID_SQL, (user_id,))
        user = cursor.fetchone()
        if user:
            self.write_json(_user_profile_dict(user))
        else:
            raise tornado.web.HTTPError(404, 'User not found')


class AdminHandler(BaseHandler):

    def get(self):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_ADMINS_SQL)
        admins = [_user_profile_dict(row) for row in cursor.fetchall()]
        self.write_json(admins)


ROUTES = [
    ('/register', RegisterHandler),
    ('/login', LoginHandler),
    ('/user/([0-9]+)', UserProfileHandler),
    ('/admin/users', AdminHandler),
]


def make_app():
    return tornado.web.Application(ROUTES)


def main():
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
