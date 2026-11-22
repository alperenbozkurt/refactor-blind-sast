import json
import sqlite3
from contextlib import contextmanager

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DB_PATH = 'cms.db'

POST_FIELDS = ('id', 'title', 'content', 'author')

STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_NOT_FOUND = 404
STATUS_SERVER_ERROR = 500

ROUTES = (
    ('get_user_posts', '/api/posts'),
    ('create_post', '/api/posts'),
    ('login', '/api/login'),
    ('delete_post', '/api/posts'),
)

CREATE_USERS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    '''

CREATE_POSTS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            published BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    '''

COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'

INSERT_USER_SQL = '''
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
        '''

INSERT_POST_SQL = '''
            INSERT INTO posts (user_id, title, content, published)
            VALUES (?, ?, ?, ?)
        '''

SELECT_USER_POSTS_SQL = '''
        SELECT p.id, p.title, p.content, u.username 
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = ?
    '''
PUBLISHED_ONLY_CLAUSE = ' AND p.published = 1'

SELECT_USER_BY_CREDENTIALS_SQL = '''
            SELECT id, username, role FROM users 
            WHERE username = ? AND password = ?
        '''

DELETE_POST_SQL = 'DELETE FROM posts WHERE id = ?'

SEED_USERS = [
    ('admin', 'admin123', 'admin'),
    ('editor1', 'editorpass', 'editor'),
    ('user1', 'userpass1', 'user'),
]

SEED_POSTS = [
    (1, 'Welcome', 'First post content', 1),
    (2, 'Editor Post', 'Editor content here', 1),
    (3, 'Draft', 'Unpublished content', 0),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

@contextmanager
def _connection():
    """Open a SQLite connection and guarantee it is closed afterwards."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _error_response(message, status):
    """Build a JSON error response with the given status code."""
    return Response(json.dumps({'error': message}), status=status)


def _create_schema(cursor):
    cursor.execute(CREATE_USERS_TABLE_SQL)
    cursor.execute(CREATE_POSTS_TABLE_SQL)


def _seed_if_empty(cursor):
    cursor.execute(COUNT_USERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_USER_SQL, SEED_USERS)
        cursor.executemany(INSERT_POST_SQL, SEED_POSTS)


def _parse_bool_param(value):
    return value.lower() == 'true'


def _row_to_post(row):
    return dict(zip(POST_FIELDS, row))


def _fetch_user_posts(user_id, show_drafts):
    query = SELECT_USER_POSTS_SQL
    if not show_drafts:
        query += PUBLISHED_ONLY_CLAUSE
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (user_id,))
        return [_row_to_post(row) for row in cursor.fetchall()]


def _insert_post(data):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            INSERT_POST_SQL,
            (data['user_id'], data['title'], data['content'],
             data.get('published', False)),
        )
        conn.commit()
        return cursor.lastrowid


def _find_user(username, password):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_USER_BY_CREDENTIALS_SQL, (username, password))
        return cursor.fetchone()


def _remove_post(post_id):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(DELETE_POST_SQL, (post_id,))
        conn.commit()
        return cursor.rowcount


# --------------------------------------------------------------------------
# Database setup
# --------------------------------------------------------------------------

def setup_database():
    with _connection() as conn:
        cursor = conn.cursor()
        _create_schema(cursor)
        _seed_if_empty(cursor)
        conn.commit()


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    user_id = request.params.get('user_id')
    show_drafts = _parse_bool_param(request.params.get('show_drafts', 'false'))
    if user_id is None:
        # Matches the error the original query produced for a missing user_id.
        return _error_response('no such column: None', STATUS_SERVER_ERROR)
    try:
        # user_id is bound as a query parameter (no SQL injection).
        return {'posts': _fetch_user_posts(user_id, show_drafts)}
    except Exception as e:
        return _error_response(str(e), STATUS_SERVER_ERROR)


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    try:
        post_id = _insert_post(request.json_body)
        return {'status': 'success', 'post_id': post_id}
    except Exception as e:
        return _error_response(str(e), STATUS_BAD_REQUEST)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    try:
        data = request.json_body
        user = _find_user(data['username'], data['password'])
        if user:
            return {'user': {'id': user[0], 'username': user[1], 'role': user[2]}}
        return _error_response('Invalid credentials', STATUS_UNAUTHORIZED)
    except Exception as e:
        return _error_response(str(e), STATUS_SERVER_ERROR)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    try:
        affected = _remove_post(request.json_body['post_id'])
        if affected == 0:
            return _error_response('Post not found', STATUS_NOT_FOUND)
        return {'status': 'success'}
    except Exception as e:
        return _error_response(str(e), STATUS_SERVER_ERROR)


# --------------------------------------------------------------------------
# Application factory
# --------------------------------------------------------------------------

def _add_routes(config):
    for name, pattern in ROUTES:
        config.add_route(name, pattern)


def main(global_config, **settings):
    setup_database()
    config = Configurator(settings=settings)
    _add_routes(config)
    config.scan()
    return config.make_wsgi_app()
