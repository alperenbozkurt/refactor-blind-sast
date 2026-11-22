from contextlib import closing, contextmanager

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
import sqlite3
import json


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DB_PATH = 'user_profiles.db'
JSON_CONTENT_TYPE = 'application/json'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                     (id INTEGER PRIMARY KEY, \n'
    '                     username TEXT UNIQUE, \n'
    '                     password TEXT, \n'
    '                     email TEXT, \n'
    '                     bio TEXT)'
)
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_SEED_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
INSERT_USER_SQL = (
    'INSERT INTO users (username, password, email, bio) VALUES (?, ?, ?, ?)'
)
SELECT_USER_BY_ID_SQL = (
    'SELECT id, username, email, bio FROM users WHERE id = ?'
)
SEARCH_USERS_SQL = (
    'SELECT id, username, email, bio FROM users '
    'WHERE username LIKE ? OR bio LIKE ?'
)

SEED_USERS = [
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
]

# Route definitions: (name, pattern)
ROUTES = (
    ('home', '/'),
    ('register', '/register'),
    ('search_users', '/search'),
    ('user_detail', '/users/{user_id}'),
)


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

@contextmanager
def get_cursor():
    """Yield a cursor on a fresh connection; the connection is always closed.

    Callers are responsible for committing when they write.
    """
    with closing(sqlite3.connect(DB_PATH)) as conn:
        yield conn, conn.cursor()


def _seed_users_if_empty(conn, cursor):
    cursor.execute(COUNT_USERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_SEED_USER_SQL, SEED_USERS)
        conn.commit()


def init_db():
    with get_cursor() as (conn, cursor):
        cursor.execute(CREATE_USERS_TABLE_SQL)
        _seed_users_if_empty(conn, cursor)


def _row_to_user(row):
    return {'id': row[0], 'username': row[1], 'email': row[2], 'bio': row[3]}


def _insert_user(data):
    with get_cursor() as (conn, cursor):
        cursor.execute(
            INSERT_USER_SQL,
            (data['username'], data['password'], data['email'],
             data.get('bio', '')),
        )
        conn.commit()


def _search_users(search_term):
    # Parameterized query: the term is bound as a value, never interpolated
    # into the SQL text.
    pattern = f'%{search_term}%'
    with get_cursor() as (_, cursor):
        cursor.execute(SEARCH_USERS_SQL, (pattern, pattern))
        return [_row_to_user(row) for row in cursor.fetchall()]


def _get_user(user_id):
    with get_cursor() as (_, cursor):
        cursor.execute(SELECT_USER_BY_ID_SQL, (user_id,))
        row = cursor.fetchone()
    return _row_to_user(row) if row else None


# --------------------------------------------------------------------------
# Response helpers
# --------------------------------------------------------------------------

def json_response(body, status=None):
    kwargs = {'content_type': JSON_CONTENT_TYPE}
    if status is not None:
        kwargs['status'] = status
    return Response(json.dumps(body), **kwargs)


def error_response(message, status):
    return json_response({'error': message}, status=status)


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

@view_config(route_name='home', request_method='GET')
def home_view(request):
    return json_response({'message': 'User Profile API'})


@view_config(route_name='register', request_method='POST')
def register_view(request):
    try:
        _insert_user(request.json_body)
        return json_response({'status': 'success'})
    except sqlite3.IntegrityError:
        return error_response('Username already exists', HTTP_BAD_REQUEST)


@view_config(route_name='search_users', request_method='GET')
def search_users_view(request):
    search_term = request.params.get('q', '')
    if not search_term:
        return error_response('Search term required', HTTP_BAD_REQUEST)
    return json_response(_search_users(search_term))


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    user = _get_user(request.matchdict['user_id'])
    if user:
        return json_response(user)
    return error_response('User not found', HTTP_NOT_FOUND)


# --------------------------------------------------------------------------
# Application factory
# --------------------------------------------------------------------------

def _add_routes(config):
    for name, pattern in ROUTES:
        config.add_route(name, pattern)


def main(global_config, **settings):
    init_db()
    config = Configurator()
    _add_routes(config)
    config.scan()
    return config.make_wsgi_app()
