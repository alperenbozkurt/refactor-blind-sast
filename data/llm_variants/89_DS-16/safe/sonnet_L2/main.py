from contextlib import contextmanager
import json
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = 'user_profiles.db'
JSON_CONTENT_TYPE = 'application/json'

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
SEARCH_USERS_SQL = (
    'SELECT id, username, email, bio FROM users '
    'WHERE username LIKE ? OR bio LIKE ?'
)
SELECT_USER_BY_ID_SQL = 'SELECT id, username, email, bio FROM users WHERE id = ?'

SEED_USERS = [
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
]

# Route definitions: (name, pattern)
ROUTE_HOME = 'home'
ROUTE_REGISTER = 'register'
ROUTE_SEARCH_USERS = 'search_users'
ROUTE_USER_DETAIL = 'user_detail'

ROUTES = (
    (ROUTE_HOME, '/'),
    (ROUTE_REGISTER, '/register'),
    (ROUTE_SEARCH_USERS, '/search'),
    (ROUTE_USER_DETAIL, '/users/{user_id}'),
)

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _db_cursor():
    """Yield (connection, cursor) for the user database and close afterwards."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn, conn.cursor()
    finally:
        conn.close()


def _json_response(payload, status=None):
    """Build a JSON response, optionally with an explicit HTTP status."""
    kwargs = {'content_type': JSON_CONTENT_TYPE}
    if status is not None:
        kwargs['status'] = status
    return Response(json.dumps(payload), **kwargs)


def _error_response(message, status):
    return _json_response({'error': message}, status=status)


def _row_to_user(row):
    return {'id': row[0], 'username': row[1], 'email': row[2], 'bio': row[3]}


def _seed_users_if_empty(conn, cursor):
    cursor.execute(COUNT_USERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_SEED_USER_SQL, SEED_USERS)
        conn.commit()


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db():
    with _db_cursor() as (conn, cursor):
        cursor.execute(CREATE_USERS_TABLE_SQL)
        _seed_users_if_empty(conn, cursor)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@view_config(route_name='home', request_method='GET')
def home_view(request):
    return _json_response({'message': 'User Profile API'})


@view_config(route_name='register', request_method='POST')
def register_view(request):
    try:
        data = request.json_body
        with _db_cursor() as (conn, cursor):
            cursor.execute(
                INSERT_USER_SQL,
                (data['username'], data['password'], data['email'],
                 data.get('bio', '')),
            )
            conn.commit()
        return _json_response({'status': 'success'})
    except sqlite3.IntegrityError:
        return _error_response('Username already exists', HTTP_BAD_REQUEST)


@view_config(route_name='search_users', request_method='GET')
def search_users_view(request):
    search_term = request.params.get('q', '')
    if not search_term:
        return _error_response('Search term required', HTTP_BAD_REQUEST)
    search_pattern = f'%{search_term}%'
    with _db_cursor() as (_, cursor):
        cursor.execute(SEARCH_USERS_SQL, (search_pattern, search_pattern))
        results = [_row_to_user(row) for row in cursor.fetchall()]
    return _json_response(results)


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    user_id = request.matchdict['user_id']
    with _db_cursor() as (_, cursor):
        cursor.execute(SELECT_USER_BY_ID_SQL, (user_id,))
        user = cursor.fetchone()
    if user:
        return _json_response(_row_to_user(user))
    return _error_response('User not found', HTTP_NOT_FOUND)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def _add_routes(config):
    for name, pattern in ROUTES:
        config.add_route(name, pattern)


def main(global_config, **settings):
    init_db()
    config = Configurator()
    _add_routes(config)
    config.scan()
    return config.make_wsgi_app()
