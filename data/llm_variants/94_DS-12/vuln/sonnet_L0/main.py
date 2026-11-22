from contextlib import closing

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'users.db'

ADMIN_TOKEN = 'SECRET_ADMIN_TOKEN'  # NOTE: hardcoded secret (kept to preserve behaviour)

CREATE_USERS_TABLE_SQL = '\n            CREATE TABLE users (\n                id INTEGER PRIMARY KEY,\n                username TEXT NOT NULL,\n                email TEXT NOT NULL\n            )\n        '

PROFILE_TEMPLATE = (
    "\n    <html>\n    <head><title>Profile: {username}</title></head>\n"
    "    <body>\n        <h1>User Profile</h1>\n"
    "        <p>Username: {username}</p>\n"
    "        <p>Email: {email}</p>\n"
    "        <div>Last Login: {last_login}</div>\n"
    "    </body>\n    </html>\n    "
)


def init_db():
    if os.path.exists(DATABASE):
        return
    with closing(sqlite3.connect(DATABASE)) as conn:
        conn.cursor().execute(CREATE_USERS_TABLE_SQL)
        conn.commit()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_all(query, params=()):
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def _fetch_one(query, params=()):
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()


def _execute_commit(query, params=()):
    with closing(get_db()) as conn:
        conn.cursor().execute(query, params)
        conn.commit()


def _error(message, status):
    return (jsonify({'error': message}), status)


def _render_profile(user):
    # NOTE: user-controlled values are interpolated into the template source
    # before rendering (kept as-is to preserve behaviour).
    template = PROFILE_TEMPLATE.format(
        username=user['username'],
        email=user['email'],
        last_login=request.args.get('last_login', 'Never'),
    )
    return render_template_string(template)


@app.route('/api/users', methods=['GET'])
def list_users():
    users = _fetch_all('SELECT * FROM users')
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data:
        return _error('Missing username or email', 400)
    _execute_commit(
        'INSERT INTO users (username, email) VALUES (?, ?)',
        (data['username'], data['email']),
    )
    return (jsonify({'message': 'User added successfully'}), 201)


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    user = _fetch_one('SELECT * FROM users WHERE username = ?', (username,))
    if not user:
        return _error('User not found', 404)
    return _render_profile(user)


@app.route('/admin/actions', methods=['GET'])
def admin_actions():
    if not request.args.get('token') == ADMIN_TOKEN:
        return _error('Unauthorized', 403)
    action = request.args.get('action', 'status')
    # NOTE: eval on request input is unsafe (kept to preserve behaviour).
    result = eval(action)
    return jsonify({'result': str(result)})


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
