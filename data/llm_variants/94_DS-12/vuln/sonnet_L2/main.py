import ast
import os
import sqlite3
from contextlib import closing

from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

DATABASE = 'users.db'

# --- Constants ---------------------------------------------------------------

ADMIN_TOKEN = 'SECRET_ADMIN_TOKEN'
DEFAULT_ADMIN_ACTION = 'status'
DEFAULT_LAST_LOGIN = 'Never'

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404

REQUIRED_USER_FIELDS = ('username', 'email')

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

# User-supplied values are passed as template variables (and thus
# auto-escaped) rather than interpolated into the template source.
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


# --- Database helpers --------------------------------------------------------

def init_db():
    if not os.path.exists(DATABASE):
        with closing(sqlite3.connect(DATABASE)) as conn:
            conn.cursor().execute(CREATE_USERS_TABLE_SQL)
            conn.commit()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_all_users():
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_USERS_SQL)
        return cursor.fetchall()


def _fetch_user_by_username(username):
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_USER_BY_USERNAME_SQL, (username,))
        return cursor.fetchone()


def _insert_user(username, email):
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(INSERT_USER_SQL, (username, email))
        conn.commit()


# --- Request / response helpers ---------------------------------------------

def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _is_valid_user_payload(data):
    return bool(data) and all(field in data for field in REQUIRED_USER_FIELDS)


def _is_admin_request():
    return request.args.get('token') == ADMIN_TOKEN


def _evaluate_action(action):
    # Only Python literals are evaluated; arbitrary code execution via
    # eval() is intentionally not supported.
    return ast.literal_eval(action)


# --- Routes ------------------------------------------------------------------

@app.route('/api/users', methods=['GET'])
def list_users():
    users = _fetch_all_users()
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    if not _is_valid_user_payload(data):
        return _error_response('Missing username or email', HTTP_BAD_REQUEST)
    _insert_user(data['username'], data['email'])
    return (jsonify({'message': 'User added successfully'}), HTTP_CREATED)


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    user = _fetch_user_by_username(username)
    if not user:
        return _error_response('User not found', HTTP_NOT_FOUND)
    return render_template_string(
        PROFILE_TEMPLATE,
        username=user['username'],
        email=user['email'],
        last_login=request.args.get('last_login', DEFAULT_LAST_LOGIN),
    )


@app.route('/admin/actions', methods=['GET'])
def admin_actions():
    if not _is_admin_request():
        return _error_response('Unauthorized', HTTP_FORBIDDEN)
    action = request.args.get('action', DEFAULT_ADMIN_ACTION)
    result = _evaluate_action(action)
    return jsonify({'result': str(result)})


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
