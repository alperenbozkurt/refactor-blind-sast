import json
import sqlite3
from contextlib import closing

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

_DB_PATH = 'user_profiles.db'

_USER_COLUMNS = ('id', 'username', 'email', 'bio')

_CREATE_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users ('
    'id INTEGER PRIMARY KEY, '
    'username TEXT UNIQUE, '
    'password TEXT, '
    'email TEXT, '
    'bio TEXT)'
)

_SEED_USERS = (
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
)

_ROUTES = (
    ('home', '/'),
    ('register', '/register'),
    ('search_users', '/search'),
    ('user_detail', '/users/{user_id}'),
)


def _connect():
    return closing(sqlite3.connect(_DB_PATH))


def _json_response(payload, status=200):
    return Response(json.dumps(payload), status=status, content_type='application/json')


def _row_to_user(row):
    return dict(zip(_USER_COLUMNS, row))


def init_db():
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(_CREATE_TABLE_SQL)
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)', _SEED_USERS)
            conn.commit()


@view_config(route_name='home', request_method='GET')
def home_view(request):
    return _json_response({'message': 'User Profile API'})


@view_config(route_name='register', request_method='POST')
def register_view(request):
    try:
        data = request.json_body
        with _connect() as conn:
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
    search_term = request.params.get('q', '')
    if not search_term:
        return _json_response({'error': 'Search term required'}, status=400)

    search_pattern = f'%{search_term}%'
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, email, bio FROM users '
            'WHERE username LIKE ? OR bio LIKE ?',
            (search_pattern, search_pattern),
        )
        results = [_row_to_user(row) for row in cursor.fetchall()]
    return _json_response(results)


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    user_id = request.matchdict['user_id']
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, email, bio FROM users WHERE id = ?',
            (user_id,),
        )
        user = cursor.fetchone()

    if user is None:
        return _json_response({'error': 'User not found'}, status=404)
    return _json_response(_row_to_user(user))


def main(global_config, **settings):
    init_db()
    config = Configurator()
    for route_name, pattern in _ROUTES:
        config.add_route(route_name, pattern)
    config.scan()
    return config.make_wsgi_app()
