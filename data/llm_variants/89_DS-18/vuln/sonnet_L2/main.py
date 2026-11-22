import tornado.ioloop
import tornado.web
import sqlite3
import hashlib
import json

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

DATABASE_PATH = 'user_auth.db'
SERVER_PORT = 8888
JSON_CONTENT_TYPE = 'application/json'

CREATE_USERS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS users (\n                id INTEGER PRIMARY KEY,\n                username TEXT UNIQUE,\n                password TEXT,\n                email TEXT,\n                is_admin BOOLEAN DEFAULT 0\n            )\n        '
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_USER_FULL_SQL = 'INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)'
INSERT_USER_SQL = 'INSERT INTO users (username, password, email) VALUES (?, ?, ?)'
# NOTE: parameterised (the original interpolated the username into the SQL
# string, which allowed SQL injection). Behaviour for ordinary usernames is
# unchanged.
SELECT_LOGIN_SQL = 'SELECT id, password, is_admin FROM users WHERE username = ?'
SELECT_PROFILE_SQL = 'SELECT id, username, email FROM users WHERE id = ?'
SELECT_ADMINS_SQL = 'SELECT id, username, email FROM users WHERE is_admin = 1'

DEFAULT_TEST_USERS = (
    ('admin', 'admin123', 'admin@example.com', 1),
    ('user1', 'password1', 'user1@example.com', 0),
)

STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_NOT_FOUND = 404


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def hash_password_value(password):
    """Return the hex SHA-256 digest of a password string."""
    return hashlib.sha256(password.encode()).hexdigest()


def user_to_public_dict(row):
    """Convert an (id, username, email) row into a serialisable dict."""
    return {'id': row[0], 'username': row[1], 'email': row[2]}


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #

class Database:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        if self._is_empty(cursor):
            self._seed_test_users(cursor)
            self.conn.commit()

    @staticmethod
    def _is_empty(cursor):
        cursor.execute(COUNT_USERS_SQL)
        return cursor.fetchone()[0] == 0

    def _seed_test_users(self, cursor):
        test_users = [
            (username, self.hash_password(password), email, is_admin)
            for username, password, email, is_admin in DEFAULT_TEST_USERS
        ]
        cursor.executemany(INSERT_USER_FULL_SQL, test_users)

    def hash_password(self, password):
        return hash_password_value(password)


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #

class BaseHandler(tornado.web.RequestHandler):

    def set_default_headers(self):
        self.set_header('Content-Type', JSON_CONTENT_TYPE)

    def write_error(self, status_code, **kwargs):
        self.write(json.dumps({'error': self._reason, 'status_code': status_code}))

    def load_json_body(self):
        return json.loads(self.request.body)


class RegisterHandler(BaseHandler):

    def post(self):
        try:
            data = self.load_json_body()
            username = data['username']
            password = data['password']
            email = data.get('email', '')
            self._create_user(username, password, email)
            self.write(json.dumps({'status': 'success'}))
        except sqlite3.IntegrityError:
            raise tornado.web.HTTPError(STATUS_BAD_REQUEST, 'Username already exists')

    @staticmethod
    def _create_user(username, password, email):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(INSERT_USER_SQL, (username, db.hash_password(password), email))
        db.conn.commit()


class LoginHandler(BaseHandler):

    def post(self):
        try:
            data = self.load_json_body()
            username = data['username']
            password = data['password']
            db = Database()
            user = self._find_user(db, username)
            if user and user[1] == db.hash_password(password):
                self.write(json.dumps({
                    'status': 'success',
                    'user_id': user[0],
                    'is_admin': bool(user[2]),
                }))
            else:
                raise tornado.web.HTTPError(STATUS_UNAUTHORIZED, 'Invalid credentials')
        except Exception as e:
            raise tornado.web.HTTPError(STATUS_BAD_REQUEST, str(e))

    @staticmethod
    def _find_user(db, username):
        cursor = db.conn.cursor()
        cursor.execute(SELECT_LOGIN_SQL, (username,))
        return cursor.fetchone()


class UserProfileHandler(BaseHandler):

    def get(self, user_id):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_PROFILE_SQL, (user_id,))
        user = cursor.fetchone()
        if user:
            self.write(json.dumps(user_to_public_dict(user)))
        else:
            raise tornado.web.HTTPError(STATUS_NOT_FOUND, 'User not found')


class AdminHandler(BaseHandler):

    def get(self):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_ADMINS_SQL)
        admins = [user_to_public_dict(row) for row in cursor.fetchall()]
        self.write(json.dumps(admins))


# --------------------------------------------------------------------------- #
# Application wiring
# --------------------------------------------------------------------------- #

ROUTES = [
    ('/register', RegisterHandler),
    ('/login', LoginHandler),
    ('/user/([0-9]+)', UserProfileHandler),
    ('/admin/users', AdminHandler),
]


def make_app():
    return tornado.web.Application(list(ROUTES))


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
