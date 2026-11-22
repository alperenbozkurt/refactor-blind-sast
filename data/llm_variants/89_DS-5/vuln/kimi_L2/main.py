"""Minimal CMS backend built on Pyramid and SQLite.

The schema is created and seeded with demo data when the application
starts.  The module is organised in three layers:

* configuration: named constants for the database, SQL statements, seed
  data, HTTP statuses and route definitions;
* data-access helpers: small functions that own connection handling and
  row mapping;
* presentation: the Pyramid view callables and the ``main`` WSGI factory.
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'cms.db'

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

STATUS_SUCCESS = 'success'
ERROR_INVALID_CREDENTIALS = 'Invalid credentials'
ERROR_POST_NOT_FOUND = 'Post not found'

POST_RESULT_COLUMNS = ('id', 'title', 'content', 'author')
USER_RESULT_COLUMNS = ('id', 'username', 'role')

SQL_CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
"""

SQL_CREATE_POSTS_TABLE = """
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        published BOOLEAN DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
"""

SQL_COUNT_USERS = 'SELECT COUNT(*) FROM users'

SQL_INSERT_USER = """
    INSERT INTO users (username, password, role)
    VALUES (?, ?, ?)
"""

SQL_INSERT_POST = """
    INSERT INTO posts (user_id, title, content, published)
    VALUES (?, ?, ?, ?)
"""

# NOTE: ``user_id`` is interpolated verbatim to preserve the exact
# behaviour of the original view.
SQL_SELECT_POSTS_BY_USER = """
    SELECT p.id, p.title, p.content, u.username
    FROM posts p
    JOIN users u ON p.user_id = u.id
    WHERE p.user_id = {user_id}
"""
SQL_FILTER_PUBLISHED = ' AND p.published = 1'

SQL_SELECT_USER_BY_CREDENTIALS = """
    SELECT id, username, role FROM users
    WHERE username = ? AND password = ?
"""

SQL_DELETE_POST = 'DELETE FROM posts WHERE id = ?'

SEED_USERS = (
    ('admin', 'admin123', 'admin'),
    ('editor1', 'editorpass', 'editor'),
    ('user1', 'userpass1', 'user'),
)

SEED_POSTS = (
    (1, 'Welcome', 'First post content', 1),
    (2, 'Editor Post', 'Editor content here', 1),
    (3, 'Draft', 'Unpublished content', 0),
)


@dataclass(frozen=True)
class Route:
    """A named route and its URL pattern."""

    name: str
    pattern: str


ROUTES = (
    Route(name='get_user_posts', pattern='/api/posts'),
    Route(name='create_post', pattern='/api/posts'),
    Route(name='login', pattern='/api/login'),
    Route(name='delete_post', pattern='/api/posts'),
)

# ---------------------------------------------------------------------------
# Parsing, mapping and response helpers
# ---------------------------------------------------------------------------


def _error_response(message, status):
    """Build the JSON error ``Response`` used by every view."""
    return Response(json.dumps({'error': message}), status=status)


def _parse_show_drafts(params):
    return params.get('show_drafts', 'false').lower() == 'true'


def _build_user_posts_query(user_id, show_drafts):
    query = SQL_SELECT_POSTS_BY_USER.format(user_id=user_id)
    if not show_drafts:
        query += SQL_FILTER_PUBLISHED
    return query


def _row_to_post(row):
    return dict(zip(POST_RESULT_COLUMNS, row))


def _row_to_user(row):
    return dict(zip(USER_RESULT_COLUMNS, row))


def _post_values(data):
    return (
        data['user_id'],
        data['title'],
        data['content'],
        data.get('published', False),
    )


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _connect():
    """Open a new connection to the CMS database."""
    return sqlite3.connect(DATABASE_PATH)


def _create_schema(cursor):
    cursor.execute(SQL_CREATE_USERS_TABLE)
    cursor.execute(SQL_CREATE_POSTS_TABLE)


def _seed_if_empty(cursor):
    cursor.execute(SQL_COUNT_USERS)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(SQL_INSERT_USER, SEED_USERS)
        cursor.executemany(SQL_INSERT_POST, SEED_POSTS)


def setup_database():
    """Create the database schema and seed it when it is empty."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        _create_schema(cursor)
        _seed_if_empty(cursor)
        conn.commit()


def _insert_post(data):
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(SQL_INSERT_POST, _post_values(data))
        conn.commit()
        return cursor.lastrowid


def _find_user_by_credentials(username, password):
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(SQL_SELECT_USER_BY_CREDENTIALS, (username, password))
        return cursor.fetchone()


def _delete_post_by_id(post_id):
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(SQL_DELETE_POST, (post_id,))
        conn.commit()
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    user_id = request.params.get('user_id')
    show_drafts = _parse_show_drafts(request.params)
    conn = _connect()
    cursor = conn.cursor()
    query = _build_user_posts_query(user_id, show_drafts)
    try:
        cursor.execute(query)
        posts = [_row_to_post(row) for row in cursor.fetchall()]
        conn.close()
        return {'posts': posts}
    except Exception as e:
        conn.close()
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    try:
        data = request.json_body
        post_id = _insert_post(data)
        return {'status': STATUS_SUCCESS, 'post_id': post_id}
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    try:
        data = request.json_body
        user = _find_user_by_credentials(data['username'], data['password'])
        if user:
            return {'user': _row_to_user(user)}
        return _error_response(ERROR_INVALID_CREDENTIALS, HTTP_UNAUTHORIZED)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    try:
        post_id = request.json_body['post_id']
        affected = _delete_post_by_id(post_id)
        if affected == 0:
            return _error_response(ERROR_POST_NOT_FOUND, HTTP_NOT_FOUND)
        return {'status': STATUS_SUCCESS}
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def _register_routes(config):
    for route in ROUTES:
        config.add_route(route.name, route.pattern)


def main(global_config, **settings):
    """Build the CMS WSGI application."""
    setup_database()
    config = Configurator(settings=settings)
    _register_routes(config)
    config.scan()
    return config.make_wsgi_app()
