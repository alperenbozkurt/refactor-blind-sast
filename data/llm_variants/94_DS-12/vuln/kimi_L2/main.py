"""User management Flask service.

Refactored for a larger codebase: configuration, SQL statements, HTML
templates and database access are isolated into named constants and small
helper functions, leaving the route handlers thin.
"""

import os
import sqlite3
from dataclasses import dataclass
from http import HTTPStatus

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""

    database_path: str = 'users.db'
    admin_token: str = 'SECRET_ADMIN_TOKEN'
    default_admin_action: str = 'status'
    default_last_login: str = 'Never'
    debug: bool = True


CONFIG = AppConfig()

# Public module-level constant kept for backwards compatibility.
DATABASE = CONFIG.database_path


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE_SQL = '''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL
            )
        '''
SELECT_ALL_USERS_SQL = 'SELECT * FROM users'
SELECT_USER_BY_USERNAME_SQL = 'SELECT * FROM users WHERE username = ?'
INSERT_USER_SQL = 'INSERT INTO users (username, email) VALUES (?, ?)'


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

PROFILE_TEMPLATE = """
    <html>
    <head><title>Profile: {username}</title></head>
    <body>
        <h1>User Profile</h1>
        <p>Username: {username}</p>
        <p>Email: {email}</p>
        <div>Last Login: {last_login}</div>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# Response messages
# ---------------------------------------------------------------------------

MSG_MISSING_FIELDS = 'Missing username or email'
MSG_USER_ADDED = 'User added successfully'
MSG_USER_NOT_FOUND = 'User not found'
MSG_UNAUTHORIZED = 'Unauthorized'


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db():
    if os.path.exists(DATABASE):
        return
    conn = sqlite3.connect(DATABASE)
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        conn.commit()
    finally:
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


def _execute_write(query, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _error_response(message, status_code):
    return jsonify({'error': message}), status_code


def _is_valid_user_payload(data):
    return bool(data) and 'username' in data and 'email' in data


def _build_profile_page(user, last_login):
    return PROFILE_TEMPLATE.format(
        username=user['username'],
        email=user['email'],
        last_login=last_login,
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
        return _error_response(MSG_MISSING_FIELDS, HTTPStatus.BAD_REQUEST)
    _execute_write(INSERT_USER_SQL, (data['username'], data['email']))
    return jsonify({'message': MSG_USER_ADDED}), HTTPStatus.CREATED


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    user = _fetch_one(SELECT_USER_BY_USERNAME_SQL, (username,))
    if not user:
        return _error_response(MSG_USER_NOT_FOUND, HTTPStatus.NOT_FOUND)
    last_login = request.args.get('last_login', CONFIG.default_last_login)
    return render_template_string(_build_profile_page(user, last_login))


@app.route('/admin/actions', methods=['GET'])
def admin_actions():
    if request.args.get('token') != CONFIG.admin_token:
        return _error_response(MSG_UNAUTHORIZED, HTTPStatus.FORBIDDEN)
    action = request.args.get('action', CONFIG.default_admin_action)
    # Behaviour preserved from the original module: the action string is
    # evaluated as a Python expression.
    result = eval(action)
    return jsonify({'result': str(result)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    init_db()
    app.run(debug=CONFIG.debug)


if __name__ == '__main__':
    main()
