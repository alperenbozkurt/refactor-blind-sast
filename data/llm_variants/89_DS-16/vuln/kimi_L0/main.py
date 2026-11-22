import json
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DB_PATH = 'user_profiles.db'

CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users ('
    'id INTEGER PRIMARY KEY, '
    'username TEXT UNIQUE, '
    'password TEXT, '
    'email TEXT, '
    'bio TEXT)'
)

DEFAULT_USERS = [
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
]

SELECT_USER_FIELDS = 'SELECT id, username, email, bio FROM users'


def get_connection():
    return sqlite3.connect(DB_PATH)


def json_response(payload, status=200):
    return Response(json.dumps(payload), status=status,
                    content_type='application/json')


def user_row_to_dict(row):
    return {'id': row[0], 'username': row[1], 'email': row[2], 'bio': row[3]}


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE)
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)',
                           DEFAULT_USERS)
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
            'INSERT INTO users (username, password, email, bio) '
            'VALUES (?, ?, ?, ?)',
            (data['username'], data['password'], data['email'],
             data.get('bio', '')),
        )
        conn.commit()
        conn.close()
        return json_response({'status': 'success'})
    except sqlite3.IntegrityError:
        return json_response({'error': 'Username already exists'}, status=400)


@view_config(route_name='search_users', request_method='GET')
def search_users_view(request):
    search_term = request.params.get('q', '')
    if not search_term:
        return json_response({'error': 'Search term required'}, status=400)
    conn = get_connection()
    cursor = conn.cursor()
    like_term = f'%{search_term}%'
    cursor.execute(
        SELECT_USER_FIELDS + ' WHERE username LIKE ? OR bio LIKE ?',
        (like_term, like_term),
    )
    results = [user_row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return json_response(results)


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    user_id = request.matchdict['user_id']
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SELECT_USER_FIELDS + ' WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return json_response(user_row_to_dict(user))
    return json_response({'error': 'User not found'}, status=404)


def main(global_config, **settings):
    init_db()
    config = Configurator()
    config.add_route('home', '/')
    config.add_route('register', '/register')
    config.add_route('search_users', '/search')
    config.add_route('user_detail', '/users/{user_id}')
    config.scan()
    return config.make_wsgi_app()
