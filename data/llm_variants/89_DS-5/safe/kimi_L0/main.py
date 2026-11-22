"""Minimal Pyramid-based CMS JSON API backed by SQLite."""

import hashlib
import json
import re
import sqlite3
from contextlib import closing

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DATABASE_PATH = 'cms.db'
MAX_TITLE_LENGTH = 200
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{4,20}$')
POST_COLUMNS = ('id', 'title', 'content', 'author')

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

SELECT_USER_POSTS_SQL = """
    SELECT p.id, p.title, p.content, u.username
    FROM posts p
    JOIN users u ON p.user_id = u.id
    WHERE p.user_id = ?
"""

SELECT_USER_BY_USERNAME_SQL = """
    SELECT id, username, role, password FROM users
    WHERE username = ?
"""

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

REQUIRED_POST_FIELDS = ('user_id', 'title', 'content')
REQUIRED_CREDENTIAL_FIELDS = ('username', 'password')


def _connect():
    """Open a new connection to the CMS database."""
    return sqlite3.connect(DATABASE_PATH)


def _hash_password(password):
    """Return the SHA-256 hex digest of the given plaintext password."""
    return hashlib.sha256(password.encode()).hexdigest()


def _json_error(message, status):
    """Build a JSON error response with the given message and status code."""
    return Response(json.dumps({'error': message}), status=status)


def _has_required_fields(data, fields):
    """Return True when every required field is present in the payload."""
    return all(field in data for field in fields)


def setup_database():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(CREATE_POSTS_TABLE_SQL)
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                INSERT_USER_SQL,
                [
                    (username, _hash_password(password), role)
                    for username, password, role in SEED_USERS
                ],
            )
            cursor.executemany(INSERT_POST_SQL, SEED_POSTS)
        conn.commit()


def validate_user_id(user_id):
    if not user_id or not user_id.isdigit():
        raise ValueError('Invalid user ID')
    return int(user_id)


@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    try:
        user_id = validate_user_id(request.params.get('user_id'))
        show_drafts = request.params.get('show_drafts', 'false').lower() == 'true'

        query = SELECT_USER_POSTS_SQL
        params = [user_id]
        if not show_drafts:
            query += ' AND p.published = 1'

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            posts = [dict(zip(POST_COLUMNS, row)) for row in cursor.fetchall()]

        return {'posts': posts}
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception:
        return _json_error('Internal server error', 500)


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    try:
        data = request.json_body
        if not _has_required_fields(data, REQUIRED_POST_FIELDS):
            return _json_error('Missing required fields', 400)

        user_id = validate_user_id(str(data['user_id']))
        if len(data['title']) > MAX_TITLE_LENGTH:
            return _json_error('Title too long', 400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM users WHERE id = ?', (user_id,))
            if not cursor.fetchone():
                return _json_error('User not found', 404)
            cursor.execute(
                INSERT_POST_SQL,
                (user_id, data['title'], data['content'], data.get('published', False)),
            )
            conn.commit()
            post_id = cursor.lastrowid

        return {'status': 'success', 'post_id': post_id}
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception:
        return _json_error('Failed to create post', 500)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    try:
        data = request.json_body
        if not _has_required_fields(data, REQUIRED_CREDENTIAL_FIELDS):
            return _json_error('Missing credentials', 400)
        if not USERNAME_PATTERN.match(data['username']):
            return _json_error('Invalid username format', 400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_USER_BY_USERNAME_SQL, (data['username'],))
            user = cursor.fetchone()

        if user and _hash_password(data['password']) == user[3]:
            return {'user': {'id': user[0], 'username': user[1], 'role': user[2]}}
        return _json_error('Invalid credentials', 401)
    except Exception:
        return _json_error('Login failed', 500)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    try:
        data = request.json_body
        if 'post_id' not in data:
            return _json_error('Missing post_id', 400)
        if not str(data['post_id']).isdigit():
            return _json_error('Invalid post ID', 400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM posts WHERE id = ?', (data['post_id'],))
            conn.commit()
            affected = cursor.rowcount

        if affected == 0:
            return _json_error('Post not found', 404)
        return {'status': 'success'}
    except Exception:
        return _json_error('Failed to delete post', 500)


def main(global_config, **settings):
    setup_database()
    config = Configurator(settings=settings)
    config.add_route('get_user_posts', '/api/posts')
    config.add_route('create_post', '/api/posts')
    config.add_route('login', '/api/login')
    config.add_route('delete_post', '/api/posts')
    config.scan()
    return config.make_wsgi_app()
