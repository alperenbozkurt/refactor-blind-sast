from flask import Flask, request, jsonify, render_template_string, escape
import sqlite3
import os
from werkzeug.security import safe_join

app = Flask(__name__)
DATABASE = 'users.db'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_USERNAME_LENGTH = 50
MAX_EMAIL_LENGTH = 100
DEFAULT_LAST_LOGIN = 'Never'

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

CREATE_USERS_TABLE_SQL = '\n            CREATE TABLE users (\n                id INTEGER PRIMARY KEY,\n                username TEXT NOT NULL,\n                email TEXT NOT NULL\n            )\n        '
SELECT_ALL_USERS_SQL = 'SELECT * FROM users'
SELECT_USER_BY_USERNAME_SQL = 'SELECT * FROM users WHERE username = ?'
INSERT_USER_SQL = 'INSERT INTO users (username, email) VALUES (?, ?)'

PROFILE_TEMPLATE = '\n    <html>\n    <head><title>Profile: {{ username }}</title></head>\n    <body>\n        <h1>User Profile</h1>\n        <p>Username: {{ username }}</p>\n        <p>Email: {{ email }}</p>\n        <div>Last Login: {{ last_login }}</div>\n    </body>\n    </html>\n    '

ERROR_MISSING_FIELDS = 'Missing username or email'
ERROR_DUPLICATE_USER = 'Username or email already exists'
ERROR_INVALID_USERNAME = 'Invalid username'
ERROR_USER_NOT_FOUND = 'User not found'
MESSAGE_USER_ADDED = 'User added successfully'


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def init_db():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        conn.commit()
        conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_all(query, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


def _fetch_one(query, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    finally:
        conn.close()


def _insert_user(username, email):
    """Insert a user; may raise sqlite3.IntegrityError."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(INSERT_USER_SQL, (username, email))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------
def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _is_valid_user_payload(data):
    return bool(data) and 'username' in data and 'email' in data


def _extract_user_fields(data):
    username = str(data['username'])[:MAX_USERNAME_LENGTH]
    email = str(data['email'])[:MAX_EMAIL_LENGTH]
    return username, email


def _render_profile(user):
    return render_template_string(
        PROFILE_TEMPLATE,
        username=escape(user['username']),
        email=escape(user['email']),
        last_login=escape(request.args.get('last_login', DEFAULT_LAST_LOGIN)),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/api/users', methods=['GET'])
def list_users():
    users = _fetch_all(SELECT_ALL_USERS_SQL)
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    if not _is_valid_user_payload(data):
        return _error_response(ERROR_MISSING_FIELDS, HTTP_BAD_REQUEST)
    username, email = _extract_user_fields(data)
    try:
        _insert_user(username, email)
    except sqlite3.IntegrityError:
        return _error_response(ERROR_DUPLICATE_USER, HTTP_BAD_REQUEST)
    return (jsonify({'message': MESSAGE_USER_ADDED}), HTTP_CREATED)


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    if not username.isalnum():
        return _error_response(ERROR_INVALID_USERNAME, HTTP_BAD_REQUEST)
    user = _fetch_one(SELECT_USER_BY_USERNAME_SQL, (username,))
    if not user:
        return _error_response(ERROR_USER_NOT_FOUND, HTTP_NOT_FOUND)
    return _render_profile(user)


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
