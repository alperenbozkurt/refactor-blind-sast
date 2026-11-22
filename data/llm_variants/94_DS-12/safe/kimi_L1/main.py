import os
import sqlite3

from flask import Flask, escape, jsonify, render_template_string, request
from werkzeug.security import safe_join

app = Flask(__name__)
DATABASE = 'users.db'


def init_db():
    """Create the users table if the database file does not exist yet."""
    if os.path.exists(DATABASE):
        return

    conn = sqlite3.connect(DATABASE)
    try:
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """Open a connection to the database with dict-like row access."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/api/users', methods=['GET'])
def list_users():
    """Return all users as a JSON list."""
    conn = get_db()
    try:
        users = conn.execute('SELECT * FROM users').fetchall()
    finally:
        conn.close()
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    """Create a new user from a JSON body containing username and email."""
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
    """Render the profile page for the given alphanumeric username."""
    if not username.isalnum():
        return jsonify({'error': 'Invalid username'}), 400

    conn = get_db()
    try:
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
    finally:
        conn.close()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    template = """
    <html>
    <head><title>Profile: {{ username }}</title></head>
    <body>
        <h1>User Profile</h1>
        <p>Username: {{ username }}</p>
        <p>Email: {{ email }}</p>
        <div>Last Login: {{ last_login }}</div>
    </body>
    </html>
    """
    return render_template_string(
        template,
        username=escape(user['username']),
        email=escape(user['email']),
        last_login=escape(request.args.get('last_login', 'Never')),
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=False)
