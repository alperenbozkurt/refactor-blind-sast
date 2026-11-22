import tornado.ioloop
import tornado.web
import sqlite3
import hashlib
import json

# ---------------------------------------------------------------------------
# Configuration / constants
# ---------------------------------------------------------------------------

DB_PATH = 'user_auth.db'
SERVER_PORT = 8888
CONTENT_TYPE_JSON = 'application/json'

CREATE_USERS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS users (\n                id INTEGER PRIMARY KEY,\n                username TEXT UNIQUE,\n                password TEXT,\n                email TEXT,\n                is_admin BOOLEAN DEFAULT 0\n            )\n        '
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_SEED_USER_SQL = 'INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)'
INSERT_USER_SQL = 'INSERT INTO users (username, password, email) VALUES (?, ?, ?)'
SELECT_CREDENTIALS_SQL = 'SELECT id, password, is_admin FROM users WHERE username = ?'
SELECT_PROFILE_SQL = 'SELECT id, username, email FROM users WHERE id = ?'
SELECT_ADMINS_SQL = 'SELECT id, username, email FROM users WHERE is_admin = 1'

# (username, plaintext password, email, is_admin)
SEED_USERS = (
    ('admin', 'admin123', 'admin@example.com', 1),
    ('user1', 'password1', 'user1@example.com', 0),
)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class Database:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        if self._is_empty(cursor):
            self._seed_users(cursor)
            self.conn.commit()

    def _is_empty(self, cursor):
        cursor.execute(COUNT_USERS_SQL)
        return cursor.fetchone()[0] == 0

    def _seed_users(self, cursor):
        test_users = [
            (username, self.hash_password(password), email, is_admin)
            for username, password, email, is_admin in SEED_USERS
        ]
        cursor.executemany(INSERT_SEED_USER_SQL, test_users)

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _user_summary(row):
    """Convert an (id, username, email) row into a response dictionary."""
    return {'id': row[0], 'username': row[1], 'email': row[2]}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class BaseHandler(tornado.web.RequestHandler):

    def set_default_headers(self):
        self.set_header('Content-Type', CONTENT_TYPE_JSON)

    def write_error(self, status_code, **kwargs):
        self.write(json.dumps({'error': self._reason, 'status_code': status_code}))

    def _json_body(self):
        return json.loads(self.request.body)

    def _write_json(self, payload):
        self.write(json.dumps(payload))


class RegisterHandler(BaseHandler):

    def post(self):
        try:
            data = self._json_body()
            username = data['username']
            password = data['password']
            email = data.get('email', '')
            self._create_user(username, password, email)
            self._write_json({'status': 'success'})
        except sqlite3.IntegrityError:
            raise tornado.web.HTTPError(400, 'Username already exists')

    @staticmethod
    def _create_user(username, password, email):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(INSERT_USER_SQL, (username, db.hash_password(password), email))
        db.conn.commit()


class LoginHandler(BaseHandler):

    def post(self):
        try:
            data = self._json_body()
            username = data['username']
            password = data['password']
            user = self._authenticate(username, password)
            if user:
                self._write_json({'status': 'success', 'user_id': user[0], 'is_admin': bool(user[2])})
            else:
                raise tornado.web.HTTPError(401, 'Invalid credentials')
        except Exception as e:
            raise tornado.web.HTTPError(400, str(e))

    @staticmethod
    def _authenticate(username, password):
        """Return the user row (id, password, is_admin) if credentials match, else None."""
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_CREDENTIALS_SQL, (username,))
        user = cursor.fetchone()
        if user and user[1] == db.hash_password(password):
            return user
        return None


class UserProfileHandler(BaseHandler):

    def get(self, user_id):
        user = self._find_user(user_id)
        if user:
            self._write_json(_user_summary(user))
        else:
            raise tornado.web.HTTPError(404, 'User not found')

    @staticmethod
    def _find_user(user_id):
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_PROFILE_SQL, (user_id,))
        return cursor.fetchone()


class AdminHandler(BaseHandler):

    def get(self):
        admins = [_user_summary(row) for row in self._fetch_admins()]
        self._write_json(admins)

    @staticmethod
    def _fetch_admins():
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_ADMINS_SQL)
        return cursor.fetchall()


# ---------------------------------------------------------------------------
# Application wiring
# ---------------------------------------------------------------------------

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
