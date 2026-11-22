import json
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DB_PATH = 'user_profiles.db'

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users
    (id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT,
    email TEXT,
    bio TEXT)
"""

INITIAL_USERS = [
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
]


def get_connection():
    """Open a new connection to the user profiles database."""
    return sqlite3.connect(DB_PATH)


def json_response(data, status=200):
    """Build a JSON Response with the given payload and HTTP status."""
    return Response(json.dumps(data), status=status, content_type='application/json')


def error_response(message, status):
    """Build a JSON error Response."""
    return json_response({'error': message}, status=status)


def public_user_dict(row):
    """Convert an (id, username, email, bio) row into a dictionary."""
    return {'id': row[0], 'username': row[1], 'email': row[2], 'bio': row[3]}


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE_SQL)
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)', INITIAL_USERS)
        conn.commit()
    conn.close()


@view_config(route_name='home', request_method='GET')
def home_view(request):
    return json_response({'message': 'User Profile API'})


@view_config(route_name='register', request_method='POST')
def register_view(request):
    try:
        data = request.json_body
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password, email, bio) VALUES (?, ?, ?, ?)',
            (data['username'], data['password'], data['email'], data.get('bio', '')),
        )
        conn.commit()
        return json_response({'status': 'success'})
    except sqlite3.IntegrityError:
        return error_response('Username already exists', 400)


@view_config(route_name='search_users', request_method='GET')
def search_users_view(request):
    search_term = request.params.get('q', '')
    if not search_term:
        return error_response('Search term required', 400)

    conn = get_connection()
    cursor = conn.cursor()
    # NOTE: the query is built by string interpolation, which is preserved
    # unchanged from the original implementation.
    query = (
        "SELECT id, username, email, bio FROM users "
        f"WHERE username LIKE '%{search_term}%' OR bio LIKE '%{search_term}%'"
    )
    cursor.execute(query)
    results = [public_user_dict(row) for row in cursor.fetchall()]
    return json_response(results)


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    user_id = request.matchdict['user_id']
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, email, bio FROM users WHERE id = ?', (user_id,)
    )
    user = cursor.fetchone()
    if user:
        return json_response(public_user_dict(user))
    return error_response('User not found', 404)


def main(global_config, **settings):
    init_db()
    config = Configurator()
    config.add_route('home', '/')
    config.add_route('register', '/register')
    config.add_route('search_users', '/search')
    config.add_route('user_detail', '/users/{user_id}')
    config.scan()
    return config.make_wsgi_app()
