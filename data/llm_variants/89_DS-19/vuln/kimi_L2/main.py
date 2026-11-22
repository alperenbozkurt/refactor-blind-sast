from dataclasses import asdict as _asdict, dataclass as _dataclass

from sanic import Sanic, response
from sanic.response import json
import asyncpg
import uuid
import datetime

_APP_NAME = 'CommentSystem'
_SERVER_HOST = '0.0.0.0'
_SERVER_PORT = 8000
_SERVER_DEBUG = True

_ROUTE_USERS = '/users'
_ROUTE_COMMENTS = '/comments'
_ROUTE_COMMENTS_SEARCH = '/comments/search'
_ROUTE_COMMENT = '/comments/<comment_id>'

_METHOD_GET = 'GET'
_METHOD_POST = 'POST'

_STATUS_CREATED = 201
_STATUS_BAD_REQUEST = 400
_STATUS_NOT_FOUND = 404

_ERROR_USER_EXISTS = 'Username or email already exists'
_ERROR_USER_NOT_FOUND = 'User not found'
_ERROR_SEARCH_TERM_REQUIRED = 'Search term required'
_ERROR_COMMENT_NOT_FOUND = 'Comment not found'

_DEFAULT_ADMIN_USERNAME = 'admin'
_DEFAULT_ADMIN_EMAIL = 'admin@example.com'

_SQL_CREATE_USERS = '\n        CREATE TABLE IF NOT EXISTS users (\n            user_id UUID PRIMARY KEY,\n            username VARCHAR(50) UNIQUE NOT NULL,\n            email VARCHAR(100) UNIQUE NOT NULL,\n            created_at TIMESTAMP DEFAULT NOW()\n        )\n    '
_SQL_CREATE_COMMENTS = '\n        CREATE TABLE IF NOT EXISTS comments (\n            comment_id UUID PRIMARY KEY,\n            user_id UUID REFERENCES users(user_id),\n            content TEXT NOT NULL,\n            created_at TIMESTAMP DEFAULT NOW(),\n            is_public BOOLEAN DEFAULT TRUE\n        )\n    '
_SQL_COUNT_USERS = 'SELECT COUNT(*) FROM users'
_SQL_INSERT_USER = 'INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)'
_SQL_INSERT_COMMENT = 'INSERT INTO comments (comment_id, user_id, content) VALUES ($1, $2, $3)'
_SQL_SELECT_PUBLIC_COMMENT = 'SELECT c.comment_id, u.username, c.content, c.created_at FROM comments c JOIN users u ON c.user_id = u.user_id WHERE c.comment_id = $1 AND c.is_public = true'


@_dataclass(frozen=True)
class _DatabaseConfig:
    user: str = 'postgres'
    password: str = 'password'
    database: str = 'comments_db'
    host: str = 'localhost'

    def as_dict(self):
        return _asdict(self)


DB_CONFIG = _DatabaseConfig().as_dict()
app = Sanic(_APP_NAME)


async def _connect():
    return await asyncpg.connect(**DB_CONFIG)


def _new_uuid():
    return str(uuid.uuid4())


def _error_response(message, status):
    return json({'error': message}, status=status)


def _serialize_comment(record):
    return {
        'comment_id': record['comment_id'],
        'username': record['username'],
        'content': record['content'],
        'created_at': record['created_at'].isoformat(),
    }


def _search_comments_query(search_term):
    return f"\n        SELECT c.comment_id, u.username, c.content, c.created_at \n        FROM comments c\n        JOIN users u ON c.user_id = u.user_id\n        WHERE c.content LIKE '%{search_term}%'\n        AND c.is_public = true\n        ORDER BY c.created_at DESC\n    "


async def init_db():
    conn = await _connect()
    await conn.execute(_SQL_CREATE_USERS)
    await conn.execute(_SQL_CREATE_COMMENTS)
    count = await conn.fetchval(_SQL_COUNT_USERS)
    if count == 0:
        await conn.execute(
            _SQL_INSERT_USER,
            _new_uuid(),
            _DEFAULT_ADMIN_USERNAME,
            _DEFAULT_ADMIN_EMAIL,
        )
    await conn.close()


@app.route(_ROUTE_USERS, methods=[_METHOD_POST])
async def create_user(request):
    data = request.json
    conn = await _connect()
    try:
        user_id = _new_uuid()
        await conn.execute(
            _SQL_INSERT_USER,
            user_id,
            data['username'],
            data['email'],
        )
        return json({'user_id': user_id}, status=_STATUS_CREATED)
    except asyncpg.UniqueViolationError:
        return _error_response(_ERROR_USER_EXISTS, _STATUS_BAD_REQUEST)
    finally:
        await conn.close()


@app.route(_ROUTE_COMMENTS, methods=[_METHOD_POST])
async def create_comment(request):
    data = request.json
    conn = await _connect()
    try:
        comment_id = _new_uuid()
        await conn.execute(
            _SQL_INSERT_COMMENT,
            comment_id,
            data['user_id'],
            data['content'],
        )
        return json({'comment_id': comment_id}, status=_STATUS_CREATED)
    except asyncpg.ForeignKeyViolationError:
        return _error_response(_ERROR_USER_NOT_FOUND, _STATUS_NOT_FOUND)
    finally:
        await conn.close()


@app.route(_ROUTE_COMMENTS_SEARCH, methods=[_METHOD_GET])
async def search_comments(request):
    search_term = request.args.get('q')
    if not search_term:
        return _error_response(_ERROR_SEARCH_TERM_REQUIRED, _STATUS_BAD_REQUEST)
    conn = await _connect()
    query = _search_comments_query(search_term)
    comments = await conn.fetch(query)
    results = []
    for record in comments:
        results.append(_serialize_comment(record))
    await conn.close()
    return json({'comments': results})


@app.route(_ROUTE_COMMENT, methods=[_METHOD_GET])
async def get_comment(request, comment_id):
    conn = await _connect()
    try:
        comment = await conn.fetchrow(_SQL_SELECT_PUBLIC_COMMENT, comment_id)
        if comment:
            return json(_serialize_comment(comment))
        return _error_response(_ERROR_COMMENT_NOT_FOUND, _STATUS_NOT_FOUND)
    finally:
        await conn.close()


if __name__ == '__main__':
    app.add_task(init_db())
    app.run(host=_SERVER_HOST, port=_SERVER_PORT, debug=_SERVER_DEBUG)
