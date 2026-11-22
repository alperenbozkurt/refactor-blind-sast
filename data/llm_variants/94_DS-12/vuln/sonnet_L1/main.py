from contextlib import closing

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'users.db'

ADMIN_TOKEN = 'SECRET_ADMIN_TOKEN'

CREATE_USERS_TABLE_SQL = '''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL
            )
        '''


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


def _error(message, status):
    return jsonify({'error': message}), status


def _build_profile_template(user):
    # NOTE: user-controlled values are interpolated directly into the template
    # source before rendering (behaviour intentionally preserved).
    lines = [
        "",
        "    <html>",
        f"    <head><title>Profile: {user['username']}</title></head>",
        "    <body>",
        "        <h1>User Profile</h1>",
        f"        <p>Username: {user['username']}</p>",
        f"        <p>Email: {user['email']}</p>",
        f"        <div>Last Login: {request.args.get('last_login', 'Never')}</div>",
        "    </body>",
        "    </html>",
        "    ",
    ]
    return "\n".join(lines)


@app.route('/api/users', methods=['GET'])
def list_users():
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data:
        return _error('Missing username or email', 400)

    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, email) VALUES (?, ?)',
            (data['username'], data['email']),
        )
        conn.commit()
    return jsonify({'message': 'User added successfully'}), 201


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

    if not user:
        return _error('User not found', 404)

    return render_template_string(_build_profile_template(user))


@app.route('/admin/actions', methods=['GET'])
def admin_actions():
    if request.args.get('token') != ADMIN_TOKEN:
        return _error('Unauthorized', 403)

    action = request.args.get('action', 'status')
    # NOTE: evaluating arbitrary input is preserved as-is from the original.
    result = eval(action)
    return jsonify({'result': str(result)})


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
