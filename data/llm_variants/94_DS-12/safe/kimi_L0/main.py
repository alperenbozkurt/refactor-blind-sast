import os
import sqlite3

from flask import Flask, escape, jsonify, render_template_string, request
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


def init_db():
    if os.path.exists(DATABASE):
        return
    conn = sqlite3.connect(DATABASE)
    try:
        conn.execute(CREATE_USERS_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/api/users', methods=['GET'])
def list_users():
    conn = get_db()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data:
        return jsonify({'error': 'Missing username or email'}), 400

    username = str(data['username'])[:50]
    email = str(data['email'])[:100]

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, email) VALUES (?, ?)',
            (username, email),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 400
    finally:
        conn.close()

    return jsonify({'message': 'User added successfully'}), 201


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    if not username.isalnum():
        return jsonify({'error': 'Invalid username'}), 400

    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return render_template_string(
        PROFILE_TEMPLATE,
        username=escape(user['username']),
        email=escape(user['email']),
        last_login=escape(request.args.get('last_login', 'Never')),
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
