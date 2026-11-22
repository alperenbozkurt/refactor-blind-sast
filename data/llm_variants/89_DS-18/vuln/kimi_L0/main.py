import hashlib
import json
import sqlite3

import tornado.ioloop
import tornado.web

DB_PATH = 'user_auth.db'

CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        is_admin BOOLEAN DEFAULT 0
    )
"""
COUNT_USERS = 'SELECT COUNT(*) FROM users'
INSERT_USER = 'INSERT INTO users (username, password, email) VALUES (?, ?, ?)'
INSERT_SEEDED_USER = (
    'INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)'
)
SELECT_USER_BY_ID = 'SELECT id, username, email FROM users WHERE id = ?'
SELECT_ADMIN_USERS = 'SELECT id, username, email FROM users WHERE is_admin = 1'

SEED_USERS = (
    ('admin', 'admin123', 'admin@example.com', 1),
    ('user1', 'password1', 'user1@example.com', 0),
)


class Database:
    """SQLite-backed user store.

    Connecting creates the users table if needed and seeds it with the
    default accounts whenever the table is empty.
    """

    def __init__(self) -> None:
        self.conn = sqlite3.connect(DB_PATH)
        self.init_db()

    def init_db(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(CREATE_USERS_TABLE)
        cursor.execute(COUNT_USERS)
        if cursor.fetchone()[0] == 0:
            test_users = [
                (username, self.hash_password(password), email, is_admin)
                for username, password, email, is_admin in SEED_USERS
            ]
            cursor.executemany(INSERT_SEEDED_USER, test_users)
            self.conn.commit()

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()


class BaseHandler(tornado.web.RequestHandler):
    """Shared JSON behaviour for the API handlers."""

    def set_default_headers(self) -> None:
        self.set_header('Content-Type', 'application/json')

    def write_json(self, payload: object) -> None:
        self.write(json.dumps(payload))

    def write_error(self, status_code: int, **kwargs) -> None:
        self.write_json({'error': self._reason, 'status_code': status_code})


class RegisterHandler(BaseHandler):

    def post(self) -> None:
        try:
            data = json.loads(self.request.body)
            username = data['username']
            password = data['password']
            email = data.get('email', '')

            db = Database()
            cursor = db.conn.cursor()
            cursor.execute(
                INSERT_USER,
                (username, db.hash_password(password), email),
            )
            db.conn.commit()
            self.write_json({'status': 'success'})
        except sqlite3.IntegrityError:
            raise tornado.web.HTTPError(400, 'Username already exists')


class LoginHandler(BaseHandler):

    def post(self) -> None:
        try:
            data = json.loads(self.request.body)
            username = data['username']
            password = data['password']

            db = Database()
            cursor = db.conn.cursor()
            # NOTE: the interpolated query is kept verbatim from the original
            # implementation to preserve its exact behaviour.
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
            # NOTE: kept from the original implementation: any failure
            # (including the 401 raised above) is reported as a 400
            # carrying the exception text.
            raise tornado.web.HTTPError(400, str(e))


class UserProfileHandler(BaseHandler):

    def get(self, user_id: str) -> None:
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_USER_BY_ID, (user_id,))
        user = cursor.fetchone()
        if user:
            self.write_json({'id': user[0], 'username': user[1], 'email': user[2]})
        else:
            raise tornado.web.HTTPError(404, 'User not found')


class AdminHandler(BaseHandler):

    def get(self) -> None:
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(SELECT_ADMIN_USERS)
        admins = [
            {'id': row[0], 'username': row[1], 'email': row[2]}
            for row in cursor.fetchall()
        ]
        self.write_json(admins)


def make_app() -> tornado.web.Application:
    return tornado.web.Application([
        ('/register', RegisterHandler),
        ('/login', LoginHandler),
        ('/user/([0-9]+)', UserProfileHandler),
        ('/admin/users', AdminHandler),
    ])


def main() -> None:
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
