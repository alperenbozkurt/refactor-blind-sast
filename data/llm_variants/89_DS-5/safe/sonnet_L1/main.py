from contextlib import closing
import hashlib
import json
import re
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DATABASE_PATH = 'cms.db'
USERNAME_PATTERN = '^[a-zA-Z0-9_]{4,20}$'
MAX_TITLE_LENGTH = 200
POST_FIELDS = ['id', 'title', 'content', 'author']

CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
"""

CREATE_POSTS_TABLE = """
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        published BOOLEAN DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
"""

INSERT_USER = """
    INSERT INTO users (username, password, role)
    VALUES (?, ?, ?)
"""

INSERT_POST = """
    INSERT INTO posts (user_id, title, content, published)
    VALUES (?, ?, ?, ?)
"""

SELECT_USER_POSTS = """
    SELECT p.id, p.title, p.content, u.username
    FROM posts p
    JOIN users u ON p.user_id = u.id
    WHERE p.user_id = ?
"""

SELECT_USER_FOR_LOGIN = """
    SELECT id, username, role, password FROM users
    WHERE username = ?
"""


def _connect():
    return sqlite3.connect(DATABASE_PATH)


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def _error_response(message, status):
    return Response(json.dumps({'error': message}), status=status)


def _has_all_keys(data, keys):
    return all(key in data for key in keys)


def _seed_database(cursor):
    cursor.executemany(INSERT_USER, [
        ('admin', _hash_password('admin123'), 'admin'),
        ('editor1', _hash_password('editorpass'), 'editor'),
        ('user1', _hash_password('userpass1'), 'user'),
    ])
    cursor.executemany(INSERT_POST, [
        (1, 'Welcome', 'First post content', 1),
        (2, 'Editor Post', 'Editor content here', 1),
        (3, 'Draft', 'Unpublished content', 0),
    ])


def setup_database():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE)
    cursor.execute(CREATE_POSTS_TABLE)
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        _seed_database(cursor)
    conn.commit()
    conn.close()


def validate_user_id(user_id):
    if not user_id or not user_id.isdigit():
        raise ValueError('Invalid user ID')
    return int(user_id)


@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    try:
        user_id = validate_user_id(request.params.get('user_id'))
        show_drafts = request.params.get('show_drafts', 'false').lower() == 'true'

        query = SELECT_USER_POSTS
        if not show_drafts:
            query += ' AND p.published = 1'

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(query, [user_id])
            posts = [dict(zip(POST_FIELDS, row)) for row in cursor.fetchall()]
        return {'posts': posts}
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Internal server error', 500)


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    try:
        data = request.json_body
        if not _has_all_keys(data, ['user_id', 'title', 'content']):
            return _error_response('Missing required fields', 400)

        user_id = validate_user_id(str(data['user_id']))
        if len(data['title']) > MAX_TITLE_LENGTH:
            return _error_response('Title too long', 400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM users WHERE id = ?', (user_id,))
            if not cursor.fetchone():
                return _error_response('User not found', 404)
            cursor.execute(INSERT_POST, (
                user_id,
                data['title'],
                data['content'],
                data.get('published', False),
            ))
            conn.commit()
            post_id = cursor.lastrowid
        return {'status': 'success', 'post_id': post_id}
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Failed to create post', 500)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    try:
        data = request.json_body
        if not _has_all_keys(data, ['username', 'password']):
            return _error_response('Missing credentials', 400)
        if not re.match(USERNAME_PATTERN, data['username']):
            return _error_response('Invalid username format', 400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_USER_FOR_LOGIN, (data['username'],))
            user = cursor.fetchone()

        if user:
            user_id, username, role, stored_hash = user
            if _hash_password(data['password']) == stored_hash:
                return {'user': {'id': user_id, 'username': username, 'role': role}}
        return _error_response('Invalid credentials', 401)
    except Exception:
        return _error_response('Login failed', 500)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    try:
        data = request.json_body
        if 'post_id' not in data:
            return _error_response('Missing post_id', 400)
        if not str(data['post_id']).isdigit():
            return _error_response('Invalid post ID', 400)

        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM posts WHERE id = ?', (data['post_id'],))
            conn.commit()
            affected = cursor.rowcount

        if affected == 0:
            return _error_response('Post not found', 404)
        return {'status': 'success'}
    except Exception:
        return _error_response('Failed to delete post', 500)


def main(global_config, **settings):
    setup_database()
    config = Configurator(settings=settings)
    config.add_route('get_user_posts', '/api/posts')
    config.add_route('create_post', '/api/posts')
    config.add_route('login', '/api/login')
    config.add_route('delete_post', '/api/posts')
    config.scan()
    return config.make_wsgi_app()
