import json
import sqlite3
from contextlib import closing

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

_DATABASE_PATH = 'cms.db'

_CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
"""

_CREATE_POSTS_TABLE = """
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        published BOOLEAN DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
"""

_SEED_USERS = (
    ('admin', 'admin123', 'admin'),
    ('editor1', 'editorpass', 'editor'),
    ('user1', 'userpass1', 'user'),
)

_SEED_POSTS = (
    (1, 'Welcome', 'First post content', 1),
    (2, 'Editor Post', 'Editor content here', 1),
    (3, 'Draft', 'Unpublished content', 0),
)

_COUNT_USERS = 'SELECT COUNT(*) FROM users'

_INSERT_USER = """
    INSERT INTO users (username, password, role)
    VALUES (?, ?, ?)
"""

_INSERT_POST = """
    INSERT INTO posts (user_id, title, content, published)
    VALUES (?, ?, ?, ?)
"""

_SELECT_USER_BY_CREDENTIALS = """
    SELECT id, username, role FROM users
    WHERE username = ? AND password = ?
"""

_DELETE_POST = 'DELETE FROM posts WHERE id = ?'

_POST_COLUMNS = ('id', 'title', 'content', 'author')

_ROUTES = (
    ('get_user_posts', '/api/posts'),
    ('create_post', '/api/posts'),
    ('login', '/api/login'),
    ('delete_post', '/api/posts'),
)


def _connect():
    """Open a new connection to the CMS database."""
    return sqlite3.connect(_DATABASE_PATH)


def _error_response(message, status):
    """Build a JSON error response with the given message and status code."""
    return Response(json.dumps({'error': message}), status=status)


def setup_database():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(_CREATE_USERS_TABLE)
        cursor.execute(_CREATE_POSTS_TABLE)
        cursor.execute(_COUNT_USERS)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(_INSERT_USER, _SEED_USERS)
            cursor.executemany(_INSERT_POST, _SEED_POSTS)
        conn.commit()


@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    user_id = request.params.get('user_id')
    show_drafts = request.params.get('show_drafts', 'false').lower() == 'true'
    conn = _connect()
    cursor = conn.cursor()
    query = f"""
        SELECT p.id, p.title, p.content, u.username
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = {user_id}
    """
    if not show_drafts:
        query += ' AND p.published = 1'
    try:
        cursor.execute(query)
        posts = [dict(zip(_POST_COLUMNS, row)) for row in cursor.fetchall()]
        return {'posts': posts}
    except Exception as e:
        return _error_response(str(e), 500)
    finally:
        conn.close()


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    try:
        data = request.json_body
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                _INSERT_POST,
                (
                    data['user_id'],
                    data['title'],
                    data['content'],
                    data.get('published', False),
                ),
            )
            conn.commit()
            post_id = cursor.lastrowid
        return {'status': 'success', 'post_id': post_id}
    except Exception as e:
        return _error_response(str(e), 400)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    try:
        data = request.json_body
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                _SELECT_USER_BY_CREDENTIALS,
                (data['username'], data['password']),
            )
            user = cursor.fetchone()
        if user:
            return {
                'user': {'id': user[0], 'username': user[1], 'role': user[2]}
            }
        return _error_response('Invalid credentials', 401)
    except Exception as e:
        return _error_response(str(e), 500)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    try:
        post_id = request.json_body['post_id']
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(_DELETE_POST, (post_id,))
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            return _error_response('Post not found', 404)
        return {'status': 'success'}
    except Exception as e:
        return _error_response(str(e), 500)


def main(global_config, **settings):
    setup_database()
    config = Configurator(settings=settings)
    for route_name, pattern in _ROUTES:
        config.add_route(route_name, pattern)
    config.scan()
    return config.make_wsgi_app()
