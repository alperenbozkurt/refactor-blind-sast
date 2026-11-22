"""Simple CMS JSON API built on Pyramid with a SQLite backend."""

import hashlib
import json
import re
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DATABASE_PATH = 'cms.db'
MAX_TITLE_LENGTH = 200
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{4,20}$')

POST_COLUMNS = ('id', 'title', 'content', 'author')
REQUIRED_POST_FIELDS = ('user_id', 'title', 'content')
REQUIRED_CREDENTIAL_FIELDS = ('username', 'password')

ROUTES = (
    ('get_user_posts', '/api/posts'),
    ('create_post', '/api/posts'),
    ('login', '/api/login'),
    ('delete_post', '/api/posts'),
)

CREATE_USERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
"""

CREATE_POSTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        published BOOLEAN DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
"""

INSERT_USER_SQL = """
    INSERT INTO users (username, password, role)
    VALUES (?, ?, ?)
"""

INSERT_POST_SQL = """
    INSERT INTO posts (user_id, title, content, published)
    VALUES (?, ?, ?, ?)
"""

COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'

SELECT_USER_POSTS_SQL = """
    SELECT p.id, p.title, p.content, u.username
    FROM posts p
    JOIN users u ON p.user_id = u.id
    WHERE p.user_id = ?
"""

PUBLISHED_FILTER_SQL = ' AND p.published = 1'

SELECT_USER_BY_ID_SQL = 'SELECT 1 FROM users WHERE id = ?'

SELECT_USER_BY_USERNAME_SQL = """
    SELECT id, username, role, password FROM users
    WHERE username = ?
"""

DELETE_POST_SQL = 'DELETE FROM posts WHERE id = ?'

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


def _connect():
    """Return a new connection to the CMS database."""
    return sqlite3.connect(DATABASE_PATH)


def _close_connection(conn):
    """Close the connection if one was opened."""
    if conn is not None:
        conn.close()


def _hash_password(password):
    """Return the stored hash representation of a plaintext password."""
    return hashlib.sha256(password.encode()).hexdigest()


def _json_error(message, status):
    """Build a JSON error response with the given HTTP status code."""
    return Response(json.dumps({'error': message}), status=status)


def setup_database():
    """Create the schema and seed default rows when the database is empty."""
    conn = _connect()
    cursor = conn.cursor()
    _create_tables(cursor)
    if _has_no_users(cursor):
        _seed_users(cursor)
        _seed_posts(cursor)
    conn.commit()
    conn.close()


def _create_tables(cursor):
    cursor.execute(CREATE_USERS_TABLE_SQL)
    cursor.execute(CREATE_POSTS_TABLE_SQL)


def _has_no_users(cursor):
    cursor.execute(COUNT_USERS_SQL)
    return cursor.fetchone()[0] == 0


def _seed_users(cursor):
    users = [
        (username, _hash_password(password), role)
        for username, password, role in SEED_USERS
    ]
    cursor.executemany(INSERT_USER_SQL, users)


def _seed_posts(cursor):
    cursor.executemany(INSERT_POST_SQL, SEED_POSTS)


def validate_user_id(user_id):
    """Return the user id as an int, rejecting empty or non-numeric input."""
    if not user_id or not user_id.isdigit():
        raise ValueError('Invalid user ID')
    return int(user_id)


@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    """List the posts for a user, optionally including unpublished drafts."""
    conn = None
    try:
        user_id = validate_user_id(request.params.get('user_id'))
        show_drafts = request.params.get('show_drafts', 'false').lower() == 'true'
        conn = _connect()
        posts = _fetch_user_posts(conn, user_id, show_drafts)
        conn.close()
        return {'posts': posts}
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception:
        _close_connection(conn)
        return _json_error('Internal server error', 500)


def _fetch_user_posts(conn, user_id, show_drafts):
    query = SELECT_USER_POSTS_SQL
    if not show_drafts:
        query += PUBLISHED_FILTER_SQL
    cursor = conn.cursor()
    cursor.execute(query, [user_id])
    return [dict(zip(POST_COLUMNS, row)) for row in cursor.fetchall()]


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    """Create a new post for an existing user."""
    conn = None
    try:
        data = request.json_body
        if not all(field in data for field in REQUIRED_POST_FIELDS):
            return _json_error('Missing required fields', 400)
        user_id = validate_user_id(str(data['user_id']))
        if len(data['title']) > MAX_TITLE_LENGTH:
            return _json_error('Title too long', 400)
        conn = _connect()
        cursor = conn.cursor()
        if not _user_exists(cursor, user_id):
            return _json_error('User not found', 404)
        cursor.execute(
            INSERT_POST_SQL,
            (user_id, data['title'], data['content'], data.get('published', False)),
        )
        conn.commit()
        post_id = cursor.lastrowid
        conn.close()
        return {'status': 'success', 'post_id': post_id}
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception:
        _close_connection(conn)
        return _json_error('Failed to create post', 500)


def _user_exists(cursor, user_id):
    cursor.execute(SELECT_USER_BY_ID_SQL, (user_id,))
    return cursor.fetchone() is not None


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    """Authenticate a user and return their public profile."""
    conn = None
    try:
        data = request.json_body
        if not all(field in data for field in REQUIRED_CREDENTIAL_FIELDS):
            return _json_error('Missing credentials', 400)
        if not USERNAME_PATTERN.match(data['username']):
            return _json_error('Invalid username format', 400)
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(SELECT_USER_BY_USERNAME_SQL, (data['username'],))
        user = cursor.fetchone()
        conn.close()
        if user and _hash_password(data['password']) == user[3]:
            return {'user': {'id': user[0], 'username': user[1], 'role': user[2]}}
        return _json_error('Invalid credentials', 401)
    except Exception:
        _close_connection(conn)
        return _json_error('Login failed', 500)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    """Delete a post by id."""
    conn = None
    try:
        data = request.json_body
        if 'post_id' not in data:
            return _json_error('Missing post_id', 400)
        if not str(data['post_id']).isdigit():
            return _json_error('Invalid post ID', 400)
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(DELETE_POST_SQL, (data['post_id'],))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            return _json_error('Post not found', 404)
        return {'status': 'success'}
    except Exception:
        _close_connection(conn)
        return _json_error('Failed to delete post', 500)


def main(global_config, **settings):
    """Set up the database and build the WSGI application."""
    setup_database()
    config = Configurator(settings=settings)
    for route_name, pattern in ROUTES:
        config.add_route(route_name, pattern)
    config.scan()
    return config.make_wsgi_app()
