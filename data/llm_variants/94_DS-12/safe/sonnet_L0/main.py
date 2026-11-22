from contextlib import closing

from flask import Flask, request, jsonify, render_template_string, escape
import sqlite3
import os
from werkzeug.security import safe_join

app = Flask(__name__)
DATABASE = 'users.db'

CREATE_USERS_TABLE_SQL = '''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL
            )
        '''

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

MAX_USERNAME_LENGTH = 50
MAX_EMAIL_LENGTH = 100


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

    username = str(data['username'])[:MAX_USERNAME_LENGTH]
    email = str(data['email'])[:MAX_EMAIL_LENGTH]

    with closing(get_db()) as conn:
        try:
            conn.cursor().execute(
                'INSERT INTO users (username, email) VALUES (?, ?)',
                (username, email),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return _error('Username or email already exists', 400)
    return jsonify({'message': 'User added successfully'}), 201


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    if not username.isalnum():
        return _error('Invalid username', 400)

    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

    if not user:
        return _error('User not found', 404)

    return render_template_string(
        PROFILE_TEMPLATE,
        username=escape(user['username']),
        email=escape(user['email']),
        last_login=escape(request.args.get('last_login', 'Never')),
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
