"""User management web service.

A small Flask application exposing a JSON API and an HTML profile page,
backed by a SQLite database.
"""

import os
import sqlite3

from flask import Flask, escape, jsonify, render_template_string, request
from werkzeug.security import safe_join

app = Flask(__name__)
DATABASE = 'users.db'

# --- SQL statements --------------------------------------------------------

CREATE_USERS_TABLE_SQL = (
    '\n            CREATE TABLE users (\n'
    '                id INTEGER PRIMARY KEY,\n'
    '                username TEXT NOT NULL,\n'
    '                email TEXT NOT NULL\n'
    '            )\n        '
)
SELECT_ALL_USERS_SQL = 'SELECT * FROM users'
SELECT_USER_BY_USERNAME_SQL = 'SELECT * FROM users WHERE username = ?'
INSERT_USER_SQL = 'INSERT INTO users (username, email) VALUES (?, ?)'

# --- Input limits ----------------------------------------------------------

MAX_USERNAME_LENGTH = 50
MAX_EMAIL_LENGTH = 100
DEFAULT_LAST_LOGIN = 'Never'

# --- HTTP status codes -----------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_CREATED = 201

# --- Response messages -----------------------------------------------------

ERROR_MISSING_USERNAME_OR_EMAIL = 'Missing username or email'
ERROR_USER_ALREADY_EXISTS = 'Username or email already exists'
ERROR_INVALID_USERNAME = 'Invalid username'
ERROR_USER_NOT_FOUND = 'User not found'
MESSAGE_USER_ADDED = 'User added successfully'

# --- Templates -------------------------------------------------------------

PROFILE_TEMPLATE = '''
    <html>
    <head><title>Profile: {{ username }}</title></head>
    <body>
        <h1>User Profile</h1>
        <p>Username: {{ username }}</p>
        <p>Email: {{ email }}</p>
        <div>Last Login: {{ last_login }}</div>
    </body>
    </html>
    '''


# --- Database helpers ------------------------------------------------------

def _create_schema():
    """Create the database file and the users table."""
    conn = sqlite3.connect(DATABASE)
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create the database schema if the database file does not exist yet."""
    if not os.path.exists(DATABASE):
        _create_schema()


def get_db():
    """Open a database connection whose rows are accessible by column name."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_all_users():
    """Return every row in the users table."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_USERS_SQL)
        return cursor.fetchall()
    finally:
        conn.close()


def _fetch_user_by_username(username):
    """Return the row for the given username, or None if it does not exist."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(SELECT_USER_BY_USERNAME_SQL, (username,))
        return cursor.fetchone()
    finally:
        conn.close()


# --- Request/response helpers ----------------------------------------------

def _error_response(message, status_code):
    """Build a JSON error response paired with the given status code."""
    return jsonify({'error': message}), status_code


def _extract_user_fields(data):
    """Validate a JSON payload and return its normalized fields.

    Returns a (username, email) tuple, or None when the payload is invalid.
    """
    if not data or 'username' not in data or 'email' not in data:
        return None
    username = str(data['username'])[:MAX_USERNAME_LENGTH]
    email = str(data['email'])[:MAX_EMAIL_LENGTH]
    return username, email


def _render_profile(user):
    """Render the HTML profile page for the given user row."""
    return render_template_string(
        PROFILE_TEMPLATE,
        username=escape(user['username']),
        email=escape(user['email']),
        last_login=escape(request.args.get('last_login', DEFAULT_LAST_LOGIN)),
    )


# --- Routes ------------------------------------------------------------------

@app.route('/api/users', methods=['GET'])
def list_users():
    users = _fetch_all_users()
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    fields = _extract_user_fields(request.get_json())
    if fields is None:
        return _error_response(ERROR_MISSING_USERNAME_OR_EMAIL, HTTP_BAD_REQUEST)
    username, email = fields
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(INSERT_USER_SQL, (username, email))
        conn.commit()
    except sqlite3.IntegrityError:
        return _error_response(ERROR_USER_ALREADY_EXISTS, HTTP_BAD_REQUEST)
    finally:
        conn.close()
    return jsonify({'message': MESSAGE_USER_ADDED}), HTTP_CREATED


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    if not username.isalnum():
        return _error_response(ERROR_INVALID_USERNAME, HTTP_BAD_REQUEST)
    user = _fetch_user_by_username(username)
    if not user:
        return _error_response(ERROR_USER_NOT_FOUND, HTTP_NOT_FOUND)
    return _render_profile(user)


# --- Entry point -------------------------------------------------------------

def main():
    init_db()
    app.run(debug=False)


if __name__ == '__main__':
    main()
