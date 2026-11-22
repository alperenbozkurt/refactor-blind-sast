"""Pyramid-based CMS API backed by a SQLite database."""

import json
import sqlite3

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

_DATABASE_PATH = 'cms.db'


def _connect():
    """Open a new connection to the CMS database."""
    return sqlite3.connect(_DATABASE_PATH)


def _error_response(message, status):
    """Build a JSON error response with the given HTTP status code."""
    return Response(json.dumps({'error': message}), status=status)


def setup_database():
    """Create the database schema if needed and seed it with default data."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            published BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
        """, [
            ('admin', 'admin123', 'admin'),
            ('editor1', 'editorpass', 'editor'),
            ('user1', 'userpass1', 'user'),
        ])
        cursor.executemany("""
            INSERT INTO posts (user_id, title, content, published)
            VALUES (?, ?, ?, ?)
        """, [
            (1, 'Welcome', 'First post content', 1),
            (2, 'Editor Post', 'Editor content here', 1),
            (3, 'Draft', 'Unpublished content', 0),
        ])

    conn.commit()
    conn.close()


@view_config(route_name='get_user_posts', request_method='GET', renderer='json')
def get_user_posts(request):
    """Return the posts belonging to the requested user."""
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
        posts = [
            dict(zip(['id', 'title', 'content', 'author'], row))
            for row in cursor.fetchall()
        ]
        conn.close()
        return {'posts': posts}
    except Exception as e:
        conn.close()
        return _error_response(str(e), 500)


@view_config(route_name='create_post', request_method='POST', renderer='json')
def create_post(request):
    """Create a new post from the JSON request body."""
    try:
        data = request.json_body
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO posts (user_id, title, content, published)
            VALUES (?, ?, ?, ?)
        """, (
            data['user_id'],
            data['title'],
            data['content'],
            data.get('published', False),
        ))
        conn.commit()
        post_id = cursor.lastrowid
        conn.close()
        return {'status': 'success', 'post_id': post_id}
    except Exception as e:
        return _error_response(str(e), 400)


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    """Authenticate a user with the credentials in the JSON request body."""
    try:
        data = request.json_body
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, role FROM users
            WHERE username = ? AND password = ?
        """, (data['username'], data['password']))
        user = cursor.fetchone()
        conn.close()
        if user:
            return {'user': {'id': user[0], 'username': user[1], 'role': user[2]}}
        return _error_response('Invalid credentials', 401)
    except Exception as e:
        return _error_response(str(e), 500)


@view_config(route_name='delete_post', request_method='DELETE', renderer='json')
def delete_post(request):
    """Delete the post identified in the JSON request body."""
    try:
        post_id = request.json_body['post_id']
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            return _error_response('Post not found', 404)
        return {'status': 'success'}
    except Exception as e:
        return _error_response(str(e), 500)


def main(global_config, **settings):
    """Create and return the CMS WSGI application."""
    setup_database()
    config = Configurator(settings=settings)
    config.add_route('get_user_posts', '/api/posts')
    config.add_route('create_post', '/api/posts')
    config.add_route('login', '/api/login')
    config.add_route('delete_post', '/api/posts')
    config.scan()
    return config.make_wsgi_app()
