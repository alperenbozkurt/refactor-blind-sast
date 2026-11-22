import json
import sqlite3
from contextlib import closing

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DB_PATH = 'user_profiles.db'

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                     (id INTEGER PRIMARY KEY, \n'
    '                     username TEXT UNIQUE, \n'
    '                     password TEXT, \n'
    '                     email TEXT, \n'
    '                     bio TEXT)'
)

SEED_USERS = [
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
]


def _connect():
    return closing(sqlite3.connect(DB_PATH))


def _json_response(payload, status=200):
    return Response(json.dumps(payload), status=status, content_type='application/json')


def _public_user(row):
    return {'id': row[0], 'username': row[1], 'email': row[2], 'bio': row[3]}


def init_db():
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)', SEED_USERS)
            conn.commit()


@view_config(route_name='home', request_method='GET')
def home_view(request):
    return _json_response({'message': 'User Profile API'})


@view_config(route_name='register', request_method='POST')
def register_view(request):
    try:
        data = request.json_body
        with _connect() as conn:
            conn.execute(
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
    pattern = f'%{search_term}%'
    with _connect() as conn:
        rows = conn.execute(
            'SELECT id, username, email, bio FROM users '
            'WHERE username LIKE ? OR bio LIKE ?',
            (pattern, pattern),
        ).fetchall()
    return _json_response([_public_user(row) for row in rows])


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    user_id = request.matchdict['user_id']
    with _connect() as conn:
        user = conn.execute(
            'SELECT id, username, email, bio FROM users WHERE id = ?',
            (user_id,),
        ).fetchone()
    if user:
        return _json_response(_public_user(user))
    return _json_response({'error': 'User not found'}, status=404)


def main(global_config, **settings):
    init_db()
    config = Configurator()
    config.add_route('home', '/')
    config.add_route('register', '/register')
    config.add_route('search_users', '/search')
    config.add_route('user_detail', '/users/{user_id}')
    config.scan()
    return config.make_wsgi_app()
