"""User Profile API — a Pyramid WSGI application backed by SQLite."""

import json
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DATABASE_PATH = 'user_profiles.db'

CREATE_USERS_TABLE = '''
CREATE TABLE IF NOT EXISTS users
    (id INTEGER PRIMARY KEY,
     username TEXT UNIQUE,
     password TEXT,
     email TEXT,
     bio TEXT)'''

SEED_USERS = [
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
]


def _connect():
    """Open a connection to the application database."""
    return sqlite3.connect(DATABASE_PATH)


def _json_response(payload, status=200):
    """Serialize *payload* into a JSON HTTP response."""
    return Response(json.dumps(payload), status=status, content_type='application/json')


def _user_to_dict(row):
    """Map a (id, username, email, bio) row to a response dictionary."""
    return {'id': row[0], 'username': row[1], 'email': row[2], 'bio': row[3]}


def init_db():
    """Create the users table if needed and seed it when empty."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE)
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)', SEED_USERS)
        conn.commit()
    conn.close()


@view_config(route_name='home', request_method='GET')
def home_view(request):
    """Return a simple API banner."""
    return _json_response({'message': 'User Profile API'})


@view_config(route_name='register', request_method='POST')
def register_view(request):
    """Create a new user from the JSON request body."""
    try:
        data = request.json_body
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password, email, bio) VALUES (?, ?, ?, ?)',
            (data['username'], data['password'], data['email'], data.get('bio', '')),
        )
        conn.commit()
        return _json_response({'status': 'success'})
    except sqlite3.IntegrityError:
        return _json_response({'error': 'Username already exists'}, status=400)


@view_config(route_name='search_users', request_method='GET')
def search_users_view(request):
    """Search users whose username or bio contains the query term."""
    search_term = request.params.get('q', '')
    if not search_term:
        return _json_response({'error': 'Search term required'}, status=400)
    conn = _connect()
    cursor = conn.cursor()
    query = (
        f"SELECT id, username, email, bio FROM users "
        f"WHERE username LIKE '%{search_term}%' OR bio LIKE '%{search_term}%'"
    )
    cursor.execute(query)
    results = [_user_to_dict(row) for row in cursor.fetchall()]
    return _json_response(results)


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    """Return a single user by id, or a 404 error when not found."""
    user_id = request.matchdict['user_id']
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, bio FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        return _json_response(_user_to_dict(user))
    return _json_response({'error': 'User not found'}, status=404)


def main(global_config, **settings):
    """Initialise the database and build the Pyramid WSGI application."""
    init_db()
    config = Configurator()
    config.add_route('home', '/')
    config.add_route('register', '/register')
    config.add_route('search_users', '/search')
    config.add_route('user_detail', '/users/{user_id}')
    config.scan()
    return config.make_wsgi_app()
