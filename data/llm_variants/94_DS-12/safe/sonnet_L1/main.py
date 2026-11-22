from flask import Flask, request, jsonify, render_template_string, escape
import sqlite3
import os
from contextlib import closing
from werkzeug.security import safe_join

app = Flask(__name__)
DATABASE = 'users.db'

USERNAME_MAX_LENGTH = 50
EMAIL_MAX_LENGTH = 100

CREATE_USERS_TABLE_SQL = '\n            CREATE TABLE users (\n                id INTEGER PRIMARY KEY,\n                username TEXT NOT NULL,\n                email TEXT NOT NULL\n            )\n        '

PROFILE_TEMPLATE = '\n    <html>\n    <head><title>Profile: {{ username }}</title></head>\n    <body>\n        <h1>User Profile</h1>\n        <p>Username: {{ username }}</p>\n        <p>Email: {{ email }}</p>\n        <div>Last Login: {{ last_login }}</div>\n    </body>\n    </html>\n    '


def init_db():
    if os.path.exists(DATABASE):
        return
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE_SQL)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def fetch_user_by_username(username):
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        return cursor.fetchone()


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
        return error_response('Missing username or email', 400)

    username = str(data['username'])[:USERNAME_MAX_LENGTH]
    email = str(data['email'])[:EMAIL_MAX_LENGTH]

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (username, email) VALUES (?, ?)',
            (username, email),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return error_response('Username or email already exists', 400)
    finally:
        conn.close()

    return (jsonify({'message': 'User added successfully'}), 201)


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    if not username.isalnum():
        return error_response('Invalid username', 400)

    user = fetch_user_by_username(username)
    if not user:
        return error_response('User not found', 404)

    return render_template_string(
        PROFILE_TEMPLATE,
        username=escape(user['username']),
        email=escape(user['email']),
        last_login=escape(request.args.get('last_login', 'Never')),
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
