from contextlib import closing
import json
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

DATABASE_PATH = 'cms.db'

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

INSERT_USER_SQL = '''
    INSERT INTO users (username, password, role)
    VALUES (?, ?, ?)
'''

INSERT_POST_SQL = '''
    INSERT INTO posts (user_id, title, content, published)
    VALUES (?, ?, ?, ?)
'''

SELECT_USER_BY_CREDENTIALS_SQL = '''
    SELECT id, username, role FROM users
    WHERE username = ? AND password = ?
'''

DEFAULT_USERS = [
    ('admin', 'admin123', 'admin'),
    ('editor1', 'editorpass', 'editor'),
    ('user1', 'userpass1', 'user'),
]

DEFAULT_POSTS = [
    (1, 'Welcome', 'First post content', 1),
    (2, 'Editor Post', 'Editor content here', 1),
    (3, 'Draft', 'Unpublished content', 0),
]

POST_FIELDS = ['id', 'title', 'content', 'author']


def _connect():
    return sqlite3.connect(DATABASE_PATH)


def _error_response(message, status):
    return Response(json.dumps({'error': message}), status=status)


def setup_database():
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(CREATE_POSTS_TABLE_SQL)
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_USER_SQL, DEFAULT_USERS)
            cursor.executemany(INSERT_POST_SQL, DEFAULT_POSTS)
        conn.commit()


@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    user_id = request.params.get('user_id')
    show_drafts = request.params.get('show_drafts', 'false').lower() == 'true'

    # NOTE: user_id is interpolated directly into the query (existing behaviour
    # preserved as-is).
    query = f'''
        SELECT p.id, p.title, p.content, u.username
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = {user_id}
    '''
    if not show_drafts:
        query += ' AND p.published = 1'

    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        posts = [dict(zip(POST_FIELDS, row)) for row in cursor.fetchall()]
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
                INSERT_POST_SQL,
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
                SELECT_USER_BY_CREDENTIALS_SQL,
                (data['username'], data['password']),
            )
            user = cursor.fetchone()
        if user:
            return {'user': {'id': user[0], 'username': user[1], 'role': user[2]}}
        return _error_response('Invalid credentials', 401)
    except Exception as e:
        return _error_response(str(e), 500)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    try:
        post_id = request.json_body['post_id']
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
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
    config.add_route('get_user_posts', '/api/posts')
    config.add_route('create_post', '/api/posts')
    config.add_route('login', '/api/login')
    config.add_route('delete_post', '/api/posts')
    config.scan()
    return config.make_wsgi_app()
