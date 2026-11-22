from contextlib import contextmanager

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
import sqlite3
import json
import hashlib
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE_PATH = 'cms.db'

USERNAME_PATTERN = '^[a-zA-Z0-9_]{4,20}$'
MAX_TITLE_LENGTH = 200

ROLE_ADMIN = 'admin'
ROLE_EDITOR = 'editor'
ROLE_USER = 'user'

POST_FIELD_NAMES = ['id', 'title', 'content', 'author']
CREATE_POST_REQUIRED_FIELDS = ['user_id', 'title', 'content']
LOGIN_REQUIRED_FIELDS = ['username', 'password']

# Seed data (used only when the users table is empty)
SEED_USERS = [
    ('admin', 'admin123', ROLE_ADMIN),
    ('editor1', 'editorpass', ROLE_EDITOR),
    ('user1', 'userpass1', ROLE_USER),
]
SEED_POSTS = [
    (1, 'Welcome', 'First post content', 1),
    (2, 'Editor Post', 'Editor content here', 1),
    (3, 'Draft', 'Unpublished content', 0),
]

# SQL statements
SQL_CREATE_USERS = '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    '''
SQL_CREATE_POSTS = '''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            published BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    '''
SQL_COUNT_USERS = 'SELECT COUNT(*) FROM users'
SQL_INSERT_USER = '''
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
        '''
SQL_INSERT_POST = '''
            INSERT INTO posts (user_id, title, content, published)
            VALUES (?, ?, ?, ?)
        '''
SQL_SELECT_USER_POSTS = '''
            SELECT p.id, p.title, p.content, u.username 
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id = ?
        '''
SQL_ONLY_PUBLISHED_CLAUSE = ' AND p.published = 1'
SQL_USER_EXISTS = 'SELECT 1 FROM users WHERE id = ?'
SQL_SELECT_USER_FOR_LOGIN = '''
            SELECT id, username, role, password FROM users 
            WHERE username = ?
        '''
SQL_DELETE_POST = 'DELETE FROM posts WHERE id = ?'

# Error messages
ERR_INVALID_USER_ID = 'Invalid user ID'
ERR_INTERNAL = 'Internal server error'
ERR_MISSING_FIELDS = 'Missing required fields'
ERR_TITLE_TOO_LONG = 'Title too long'
ERR_USER_NOT_FOUND = 'User not found'
ERR_CREATE_FAILED = 'Failed to create post'
ERR_MISSING_CREDENTIALS = 'Missing credentials'
ERR_INVALID_USERNAME = 'Invalid username format'
ERR_INVALID_CREDENTIALS = 'Invalid credentials'
ERR_LOGIN_FAILED = 'Login failed'
ERR_MISSING_POST_ID = 'Missing post_id'
ERR_INVALID_POST_ID = 'Invalid post ID'
ERR_POST_NOT_FOUND = 'Post not found'
ERR_DELETE_FAILED = 'Failed to delete post'


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

@contextmanager
def _connection():
    """Open a connection to the CMS database and always close it."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def _error_response(message, status):
    return Response(json.dumps({'error': message}), status=status)


def _has_all_keys(data, keys):
    return all((key in data for key in keys))


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def _create_tables(cursor):
    cursor.execute(SQL_CREATE_USERS)
    cursor.execute(SQL_CREATE_POSTS)


def _seed_database(cursor):
    users = [
        (username, _hash_password(password), role)
        for username, password, role in SEED_USERS
    ]
    cursor.executemany(SQL_INSERT_USER, users)
    cursor.executemany(SQL_INSERT_POST, SEED_POSTS)


def setup_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    _create_tables(cursor)
    cursor.execute(SQL_COUNT_USERS)
    if cursor.fetchone()[0] == 0:
        _seed_database(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_user_id(user_id):
    if not user_id or not user_id.isdigit():
        raise ValueError(ERR_INVALID_USER_ID)
    return int(user_id)


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def _fetch_user_posts(user_id, show_drafts):
    query = SQL_SELECT_USER_POSTS
    if not show_drafts:
        query += SQL_ONLY_PUBLISHED_CLAUSE
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, [user_id])
        return [dict(zip(POST_FIELD_NAMES, row)) for row in cursor.fetchall()]


def _user_exists(cursor, user_id):
    cursor.execute(SQL_USER_EXISTS, (user_id,))
    return bool(cursor.fetchone())


def _find_user_by_username(username):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SQL_SELECT_USER_FOR_LOGIN, (username,))
        return cursor.fetchone()


def _delete_post_by_id(post_id):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SQL_DELETE_POST, (post_id,))
        conn.commit()
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    try:
        user_id = validate_user_id(request.params.get('user_id'))
        show_drafts = request.params.get('show_drafts', 'false').lower() == 'true'
        posts = _fetch_user_posts(user_id, show_drafts)
        return {'posts': posts}
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(ERR_INTERNAL, 500)


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    try:
        data = request.json_body
        if not _has_all_keys(data, CREATE_POST_REQUIRED_FIELDS):
            return _error_response(ERR_MISSING_FIELDS, 400)
        user_id = validate_user_id(str(data['user_id']))
        if len(data['title']) > MAX_TITLE_LENGTH:
            return _error_response(ERR_TITLE_TOO_LONG, 400)
        with _connection() as conn:
            cursor = conn.cursor()
            if not _user_exists(cursor, user_id):
                return _error_response(ERR_USER_NOT_FOUND, 404)
            cursor.execute(
                SQL_INSERT_POST,
                (user_id, data['title'], data['content'], data.get('published', False)),
            )
            conn.commit()
            post_id = cursor.lastrowid
        return {'status': 'success', 'post_id': post_id}
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(ERR_CREATE_FAILED, 500)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    try:
        data = request.json_body
        if not _has_all_keys(data, LOGIN_REQUIRED_FIELDS):
            return _error_response(ERR_MISSING_CREDENTIALS, 400)
        if not re.match(USERNAME_PATTERN, data['username']):
            return _error_response(ERR_INVALID_USERNAME, 400)
        user = _find_user_by_username(data['username'])
        if user:
            hashed_input = _hash_password(data['password'])
            if hashed_input == user[3]:
                return {'user': {'id': user[0], 'username': user[1], 'role': user[2]}}
        return _error_response(ERR_INVALID_CREDENTIALS, 401)
    except Exception:
        return _error_response(ERR_LOGIN_FAILED, 500)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    try:
        data = request.json_body
        if 'post_id' not in data:
            return _error_response(ERR_MISSING_POST_ID, 400)
        if not str(data['post_id']).isdigit():
            return _error_response(ERR_INVALID_POST_ID, 400)
        affected = _delete_post_by_id(data['post_id'])
        if affected == 0:
            return _error_response(ERR_POST_NOT_FOUND, 404)
        return {'status': 'success'}
    except Exception:
        return _error_response(ERR_DELETE_FAILED, 500)


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

ROUTES = [
    ('get_user_posts', '/api/posts'),
    ('create_post', '/api/posts'),
    ('login', '/api/login'),
    ('delete_post', '/api/posts'),
]


def _add_routes(config):
    for name, pattern in ROUTES:
        config.add_route(name, pattern)


def main(global_config, **settings):
    setup_database()
    config = Configurator(settings=settings)
    _add_routes(config)
    config.scan()
    return config.make_wsgi_app()
