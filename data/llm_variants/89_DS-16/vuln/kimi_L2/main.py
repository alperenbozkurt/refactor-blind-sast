"""User Profile API.

A small Pyramid WSGI application backed by a SQLite database of user
profiles. The module is organised into four parts:

* configuration -- named constants, seed data and route definitions,
* data access   -- helpers wrapping every interaction with SQLite,
* presentation  -- helpers for building JSON responses,
* views / setup -- the Pyramid view callables, ``init_db`` and the
  ``main`` WSGI application factory.
"""

import json
import sqlite3
from dataclasses import dataclass

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'user_profiles.db'
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
SELECT_USER_BY_ID_SQL = (
    'SELECT id, username, email, bio FROM users WHERE id = ?'
)
# Interpolation (rather than bound parameters) is kept deliberately so the
# generated query string is identical to the original implementation.
SEARCH_USERS_SQL_TEMPLATE = (
    "SELECT id, username, email, bio FROM users "
    "WHERE username LIKE '%{search_term}%' OR bio LIKE '%{search_term}%'"
)

SEED_USERS = (
    (1, 'admin', 'securepass123', 'admin@example.com', 'System administrator'),
    (2, 'johndoe', 'johnspass', 'john@example.com', 'Software developer'),
    (3, 'janedoe', 'janespass', 'jane@example.com', 'Data scientist'),
)


@dataclass(frozen=True)
class Route:
    """A named route and the URL pattern it is mounted on."""

    name: str
    pattern: str


ROUTES = (
    Route('home', '/'),
    Route('register', '/register'),
    Route('search_users', '/search'),
    Route('user_detail', '/users/{user_id}'),
)


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

def get_connection():
    """Open a new connection to the application's SQLite database."""
    return sqlite3.connect(DATABASE_PATH)


def insert_user(username, password, email, bio):
    """Insert a user row, propagating ``sqlite3.IntegrityError`` on conflicts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(INSERT_USER_SQL, (username, password, email, bio))
    conn.commit()


def find_users(search_term):
    """Return user rows whose username or bio matches *search_term*."""
    conn = get_connection()
    cursor = conn.cursor()
    query = SEARCH_USERS_SQL_TEMPLATE.format(search_term=search_term)
    cursor.execute(query)
    return cursor.fetchall()


def find_user_by_id(user_id):
    """Return the user row for *user_id*, or ``None`` when it does not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SELECT_USER_BY_ID_SQL, (user_id,))
    return cursor.fetchone()


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def json_response(payload, status=200):
    """Serialize *payload* into a JSON :class:`Response`."""
    return Response(json.dumps(payload), status=status,
                    content_type=JSON_CONTENT_TYPE)


def user_row_to_dict(row):
    """Convert an ``(id, username, email, bio)`` row into a JSON mapping."""
    return {'id': row[0], 'username': row[1], 'email': row[2], 'bio': row[3]}


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db():
    """Create the users table when missing and seed it when it is empty."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE_SQL)
    cursor.execute(COUNT_USERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_SEED_USER_SQL, SEED_USERS)
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@view_config(route_name='home', request_method='GET')
def home_view(request):
    return json_response({'message': 'User Profile API'})


@view_config(route_name='register', request_method='POST')
def register_view(request):
    try:
        data = request.json_body
        insert_user(data['username'], data['password'], data['email'],
                    data.get('bio', ''))
        return json_response({'status': 'success'})
    except sqlite3.IntegrityError:
        return json_response({'error': 'Username already exists'}, status=400)


@view_config(route_name='search_users', request_method='GET')
def search_users_view(request):
    search_term = request.params.get('q', '')
    if not search_term:
        return json_response({'error': 'Search term required'}, status=400)
    results = [user_row_to_dict(row) for row in find_users(search_term)]
    return json_response(results)


@view_config(route_name='user_detail', request_method='GET')
def user_detail_view(request):
    user = find_user_by_id(request.matchdict['user_id'])
    if user:
        return json_response(user_row_to_dict(user))
    else:
        return json_response({'error': 'User not found'}, status=404)


# ---------------------------------------------------------------------------
# WSGI application factory
# ---------------------------------------------------------------------------

def main(global_config, **settings):
    init_db()
    config = Configurator()
    for route in ROUTES:
        config.add_route(route.name, route.pattern)
    config.scan()
    return config.make_wsgi_app()
