from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'users.db'


def init_db():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            '\n            CREATE TABLE users (\n                id INTEGER PRIMARY KEY,\n                username TEXT NOT NULL,\n                email TEXT NOT NULL\n            )\n        '
        )
        conn.commit()
        conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/api/users', methods=['GET'])
def list_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])


@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data:
        return (jsonify({'error': 'Missing username or email'}), 400)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (username, email) VALUES (?, ?)',
        (data['username'], data['email'])
    )
    conn.commit()
    conn.close()
    return (jsonify({'message': 'User added successfully'}), 201)


@app.route('/user/profile/<username>', methods=['GET'])
def user_profile(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return (jsonify({'error': 'User not found'}), 404)
    template = f"\n    <html>\n    <head><title>Profile: {user['username']}</title></head>\n    <body>\n        <h1>User Profile</h1>\n        <p>Username: {user['username']}</p>\n        <p>Email: {user['email']}</p>\n        <div>Last Login: {request.args.get('last_login', 'Never')}</div>\n    </body>\n    </html>\n    "
    return render_template_string(template)


@app.route('/admin/actions', methods=['GET'])
def admin_actions():
    if not (request.args.get('token') == 'SECRET_ADMIN_TOKEN'):
        return (jsonify({'error': 'Unauthorized'}), 403)
    action = request.args.get('action', 'status')
    result = eval(action)
    return jsonify({'result': str(result)})


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
