"""User Profile API.

A small Pyramid WSGI application backed by SQLite that lets clients
register users and search or retrieve public user profiles.
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Dict, Sequence

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DATABASE_PATH = 'user_profiles.db'
JSON_CONTENT_TYPE = 'application/json'

# Route names.
ROUTE_HOME = 'home'
ROUTE_REGISTER = 'register'
ROUTE_SEARCH_USERS = 'search_users'
ROUTE_USER_DETAIL = 'user_detail'

# Route patterns.
PATTERN_HOME = '/'
PATTERN_REGISTER = '/register'
PATTERN_SEARCH_USERS = '/search'
PATTERN_USER_DETAIL = '/users/{user_id}'

# (route name, pattern) pairs registered by ``main``.
ROUTES = (
    (ROUTE_HOME, PATTERN_HOME),
    (ROUTE_REGISTER, PATTERN_REGISTER),
    (ROUTE_SEARCH_USERS, PATTERN_SEARCH_USERS),
    (ROUTE_USER_DETAIL, PATTERN_USER_DETAIL),
)

# HTTP statuses returned by the API.
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

# Response messages.
MESSAGE_HOME = 'User Profile API'
STATUS_SUCCESS = 'success'
ERROR_USERNAME_EXISTS = 'Username already exists'
ERROR_SEARCH_TERM_REQUIRED = 'Search term required'
ERROR_USER_NOT_FOUND = 'User not found'

# SQL statements.
CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n                     (id INTEGER PRIMARY KEY, \n                     username TEXT UNIQUE, \n                     password TEXT, \n                     email TEXT, \n                     bio TEXT)'
)
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_SEED_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
INSERT_USER_SQL = (
    'INSERT INTO users (username, password, email, bio) '
    'VALUES (?, ?, ?, ?)'
)
SEARCH_USERS_SQL = (
    'SELECT id, username, email, bio FROM users '
    'WHERE username LIKE ? OR bio LIKE ?'
)
SELECT_USER_BY_ID_SQL = (
    'SELECT id, username, email, bio FROM users WHERE id = ?'
)

# Rows inserted the first time the database is created.
SEED_USERS = (
    (1, 'admin', 'securepass123', 'admin@example.com',
     'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
)


@dataclass(frozen=True)
class DatabaseConfig:
    """Settings required to open the user profiles database."""

    path: str = DATABASE_PATH


DEFAULT_DATABASE_CONFIG = DatabaseConfig()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect(
    config: DatabaseConfig = DEFAULT_DATABASE_CONFIG,
) -> sqlite3.Connection:
    """Open a new SQLite connection using ``config``."""
    return sqlite3.connect(config.path)


def _json_response(payload: Any, status: int = HTTP_OK) -> Response:
    """Serialize ``payload`` into a JSON response."""
    return Response(
        json.dumps(payload),
        status=status,
        content_type=JSON_CONTENT_TYPE,
    )


def _json_error(message: str, status: int) -> Response:
    """Build a JSON response carrying a single ``error`` message."""
    return _json_response({'error': message}, status=status)


def _user_row_to_dict(row: Sequence[Any]) -> Dict[str, Any]:
    """Map a ``(id, username, email, bio)`` row to its API representation."""
    return {
        'id': row[0],
        'username': row[1],
        'email': row[2],
        'bio': row[3],
    }


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def init_db():
    """Create the users table if needed and seed it when it is empty."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(COUNT_USERS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_SEED_USER_SQL, SEED_USERS)
            conn.commit()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@view_config(route_name=ROUTE_HOME, request_method='GET')
def home_view(request):
    """Return a short description of the API."""
    return _json_response({'message': MESSAGE_HOME})


@view_config(route_name=ROUTE_REGISTER, request_method='POST')
def register_view(request):
    """Create a new user from the JSON request body."""
    try:
        data = request.json_body
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                INSERT_USER_SQL,
                (
                    data['username'],
                    data['password'],
                    data['email'],
                    data.get('bio', ''),
                ),
            )
            conn.commit()
        return _json_response({'status': STATUS_SUCCESS})
    except sqlite3.IntegrityError:
        return _json_error(ERROR_USERNAME_EXISTS, status=HTTP_BAD_REQUEST)


@view_config(route_name=ROUTE_SEARCH_USERS, request_method='GET')
def search_users_view(request):
    """Search users by username or bio using the ``q`` query parameter."""
    search_term = request.params.get('q', '')
    if not search_term:
        return _json_error(ERROR_SEARCH_TERM_REQUIRED, status=HTTP_BAD_REQUEST)
    search_pattern = f'%{search_term}%'
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(SEARCH_USERS_SQL, (search_pattern, search_pattern))
        results = [_user_row_to_dict(row) for row in cursor.fetchall()]
    return _json_response(results)


@view_config(route_name=ROUTE_USER_DETAIL, request_method='GET')
def user_detail_view(request):
    """Return the public profile of the user identified in the URL."""
    user_id = request.matchdict['user_id']
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_USER_BY_ID_SQL, (user_id,))
        user = cursor.fetchone()
    if user:
        return _json_response(_user_row_to_dict(user))
    else:
        return _json_error(ERROR_USER_NOT_FOUND, status=HTTP_NOT_FOUND)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def main(global_config, **settings):
    """Initialise the database and build the WSGI application."""
    init_db()
    config = Configurator()
    for route_name, pattern in ROUTES:
        config.add_route(route_name, pattern)
    config.scan()
    return config.make_wsgi_app()
