"""Minimal JSON CMS API built on Pyramid and SQLite.

Public module-level names (kept stable for consumers):

    setup_database, validate_user_id,
    get_user_posts, create_post, login, delete_post, main
"""

import hashlib
import json
import re
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'cms.db'

# (route name, URL path) pairs, registered in declaration order.
ROUTES = (
    ('get_user_posts', '/api/posts'),
    ('create_post', '/api/posts'),
    ('login', '/api/login'),
    ('delete_post', '/api/posts'),
)

MAX_TITLE_LENGTH = 200
USERNAME_PATTERN = r'^[a-zA-Z0-9_]{4,20}$'

REQUIRED_POST_FIELDS = ('user_id', 'title', 'content')
REQUIRED_LOGIN_FIELDS = ('username', 'password')

# Column names used to build the post dictionaries returned to clients.
POST_RESPONSE_COLUMNS = ('id', 'title', 'content', 'author')

# HTTP status codes used by the API.
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500


# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------

ERROR_INVALID_USER_ID = 'Invalid user ID'
ERROR_MISSING_FIELDS = 'Missing required fields'
ERROR_TITLE_TOO_LONG = 'Title too long'
ERROR_USER_NOT_FOUND = 'User not found'
ERROR_INTERNAL_SERVER = 'Internal server error'
ERROR_CREATE_POST_FAILED = 'Failed to create post'
ERROR_MISSING_CREDENTIALS = 'Missing credentials'
ERROR_INVALID_USERNAME_FORMAT = 'Invalid username format'
ERROR_INVALID_CREDENTIALS = 'Invalid credentials'
ERROR_LOGIN_FAILED = 'Login failed'
ERROR_MISSING_POST_ID = 'Missing post_id'
ERROR_INVALID_POST_ID = 'Invalid post ID'
ERROR_POST_NOT_FOUND = 'Post not found'
ERROR_DELETE_POST_FAILED = 'Failed to delete post'


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

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

SQL_INSERT_USER = (
    'INSERT INTO users (username, password, role) VALUES (?, ?, ?)'
)

SQL_INSERT_POST = (
    'INSERT INTO posts (user_id, title, content, published) VALUES (?, ?, ?, ?)'
)

SQL_SELECT_POSTS_BY_USER = """
    SELECT p.id, p.title, p.content, u.username
    FROM posts p
    JOIN users u ON p.user_id = u.id
    WHERE p.user_id = ?
"""

SQL_PUBLISHED_ONLY = ' AND p.published = 1'

SQL_SELECT_USER_EXISTS = 'SELECT 1 FROM users WHERE id = ?'

SQL_SELECT_USER_BY_USERNAME = (
    'SELECT id, username, role, password FROM users WHERE username = ?'
)

SQL_DELETE_POST_BY_ID = 'DELETE FROM posts WHERE id = ?'


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# (username, plain-text password, role); passwords are hashed before insert.
SEED_USERS = (
    ('admin', 'admin123', 'admin'),
    ('editor1', 'editorpass', 'editor'),
    ('user1', 'userpass1', 'user'),
)

# (user_id, title, content, published)
SEED_POSTS = (
    (1, 'Welcome', 'First post content', 1),
    (2, 'Editor Post', 'Editor content here', 1),
    (3, 'Draft', 'Unpublished content', 0),
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _connect():
    """Open a new SQLite connection to the CMS database."""
    return sqlite3.connect(DATABASE_PATH)


def _close_connection(conn):
    """Close *conn* if a connection was opened."""
    if conn is not None:
        conn.close()


def _hash_password(password):
    """Return the SHA-256 hex digest of *password*."""
    return hashlib.sha256(password.encode()).hexdigest()


def _json_error(message, status):
    """Build a JSON ``{"error": ...}`` response with the given status."""
    return Response(json.dumps({'error': message}), status=status)


def _has_keys(data, keys):
    """Return True when every one of *keys* is present in *data*."""
    return all(key in data for key in keys)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def _seed_users(cursor):
    """Insert the default users with hashed passwords."""
    hashed_users = [
        (username, _hash_password(password), role)
        for username, password, role in SEED_USERS
    ]
    cursor.executemany(SQL_INSERT_USER, hashed_users)


def _seed_posts(cursor):
    """Insert the default posts."""
    cursor.executemany(SQL_INSERT_POST, SEED_POSTS)


def setup_database():
    """Create the schema, seeding default rows when the DB is empty."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(SQL_CREATE_USERS_TABLE)
    cursor.execute(SQL_CREATE_POSTS_TABLE)
    cursor.execute(SQL_COUNT_USERS)
    if cursor.fetchone()[0] == 0:
        _seed_users(cursor)
        _seed_posts(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_user_id(user_id):
    """Return *user_id* as an ``int`` or raise ``ValueError``."""
    if not user_id or not user_id.isdigit():
        raise ValueError(ERROR_INVALID_USER_ID)
    return int(user_id)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    conn = None
    try:
        user_id = validate_user_id(request.params.get('user_id'))
        show_drafts = request.params.get('show_drafts', 'false').lower() == 'true'
        conn = _connect()
        cursor = conn.cursor()
        query = SQL_SELECT_POSTS_BY_USER
        params = [user_id]
        if not show_drafts:
            query += SQL_PUBLISHED_ONLY
        cursor.execute(query, params)
        posts = [dict(zip(POST_RESPONSE_COLUMNS, row)) for row in cursor.fetchall()]
        conn.close()
        return {'posts': posts}
    except ValueError as e:
        return _json_error(str(e), HTTP_BAD_REQUEST)
    except Exception:
        _close_connection(conn)
        return _json_error(ERROR_INTERNAL_SERVER, HTTP_INTERNAL_SERVER_ERROR)


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    conn = None
    try:
        data = request.json_body
        if not _has_keys(data, REQUIRED_POST_FIELDS):
            return _json_error(ERROR_MISSING_FIELDS, HTTP_BAD_REQUEST)
        user_id = validate_user_id(str(data['user_id']))
        if len(data['title']) > MAX_TITLE_LENGTH:
            return _json_error(ERROR_TITLE_TOO_LONG, HTTP_BAD_REQUEST)
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(SQL_SELECT_USER_EXISTS, (user_id,))
        if not cursor.fetchone():
            conn.close()
            return _json_error(ERROR_USER_NOT_FOUND, HTTP_NOT_FOUND)
        cursor.execute(
            SQL_INSERT_POST,
            (user_id, data['title'], data['content'], data.get('published', False)),
        )
        conn.commit()
        post_id = cursor.lastrowid
        conn.close()
        return {'status': 'success', 'post_id': post_id}
    except ValueError as e:
        return _json_error(str(e), HTTP_BAD_REQUEST)
    except Exception:
        _close_connection(conn)
        return _json_error(ERROR_CREATE_POST_FAILED, HTTP_INTERNAL_SERVER_ERROR)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    conn = None
    try:
        data = request.json_body
        if not _has_keys(data, REQUIRED_LOGIN_FIELDS):
            return _json_error(ERROR_MISSING_CREDENTIALS, HTTP_BAD_REQUEST)
        if not re.match(USERNAME_PATTERN, data['username']):
            return _json_error(ERROR_INVALID_USERNAME_FORMAT, HTTP_BAD_REQUEST)
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(SQL_SELECT_USER_BY_USERNAME, (data['username'],))
        user = cursor.fetchone()
        conn.close()
        if user and _hash_password(data['password']) == user[3]:
            return {'user': {'id': user[0], 'username': user[1], 'role': user[2]}}
        return _json_error(ERROR_INVALID_CREDENTIALS, HTTP_UNAUTHORIZED)
    except Exception:
        _close_connection(conn)
        return _json_error(ERROR_LOGIN_FAILED, HTTP_INTERNAL_SERVER_ERROR)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    conn = None
    try:
        data = request.json_body
        if 'post_id' not in data:
            return _json_error(ERROR_MISSING_POST_ID, HTTP_BAD_REQUEST)
        if not str(data['post_id']).isdigit():
            return _json_error(ERROR_INVALID_POST_ID, HTTP_BAD_REQUEST)
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(SQL_DELETE_POST_BY_ID, (data['post_id'],))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            return _json_error(ERROR_POST_NOT_FOUND, HTTP_NOT_FOUND)
        return {'status': 'success'}
    except Exception:
        _close_connection(conn)
        return _json_error(ERROR_DELETE_POST_FAILED, HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# WSGI application factory
# ---------------------------------------------------------------------------

def main(global_config, **settings):
    """Create and configure the WSGI application."""
    setup_database()
    config = Configurator(settings=settings)
    for route_name, path in ROUTES:
        config.add_route(route_name, path)
    config.scan()
    return config.make_wsgi_app()
