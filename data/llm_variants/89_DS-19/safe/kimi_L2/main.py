"""Comment system API built with Sanic and asyncpg.

The module is organised into small, focused pieces:

* named constants for configuration values, SQL statements and messages
* helper functions for database access and record serialisation
* thin route handlers that keep the original behaviour intact
"""

from sanic import Sanic, response
from sanic.response import json
import asyncpg
import uuid
import datetime

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

APP_NAME = 'CommentSystem'

app = Sanic(APP_NAME)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_CONFIG = {
    'user': 'postgres',
    'password': 'password',
    'database': 'comments_db',
    'host': 'localhost',
}

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SERVER_DEBUG = True

DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_EMAIL = 'admin@example.com'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

SQL_CREATE_USERS_TABLE = '''
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    '''

SQL_CREATE_COMMENTS_TABLE = '''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(user_id),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            is_public BOOLEAN DEFAULT TRUE
        )
    '''

SQL_COUNT_USERS = 'SELECT COUNT(*) FROM users'

SQL_INSERT_USER = (
    'INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)'
)

SQL_INSERT_COMMENT = (
    'INSERT INTO comments (comment_id, user_id, content) VALUES ($1, $2, $3)'
)

SQL_SEARCH_PUBLIC_COMMENTS = '''
        SELECT c.comment_id, u.username, c.content, c.created_at 
        FROM comments c
        JOIN users u ON c.user_id = u.user_id
        WHERE c.content LIKE $1
        AND c.is_public = true
        ORDER BY c.created_at DESC
    '''

SQL_SELECT_PUBLIC_COMMENT = (
    'SELECT c.comment_id, u.username, c.content, c.created_at '
    'FROM comments c '
    'JOIN users u ON c.user_id = u.user_id '
    'WHERE c.comment_id = $1 AND c.is_public = true'
)

# ---------------------------------------------------------------------------
# Response messages
# ---------------------------------------------------------------------------

ERROR_USERNAME_OR_EMAIL_EXISTS = 'Username or email already exists'
ERROR_USER_NOT_FOUND = 'User not found'
ERROR_SEARCH_TERM_REQUIRED = 'Search term required'
ERROR_COMMENT_NOT_FOUND = 'Comment not found'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def get_db_connection():
    """Return a new database connection using ``DB_CONFIG``."""
    return await asyncpg.connect(**DB_CONFIG)


def build_search_pattern(search_term):
    """Wrap a raw search term in a SQL ``LIKE`` pattern."""
    return f'%{search_term}%'


def serialize_comment(record):
    """Convert a comment record into a JSON-serialisable dictionary."""
    return {
        'comment_id': record['comment_id'],
        'username': record['username'],
        'content': record['content'],
        'created_at': record['created_at'].isoformat(),
    }

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

async def init_db():
    conn = await get_db_connection()
    await conn.execute(SQL_CREATE_USERS_TABLE)
    await conn.execute(SQL_CREATE_COMMENTS_TABLE)
    user_count = await conn.fetchval(SQL_COUNT_USERS)
    if user_count == 0:
        await conn.execute(
            SQL_INSERT_USER,
            str(uuid.uuid4()),
            DEFAULT_ADMIN_USERNAME,
            DEFAULT_ADMIN_EMAIL,
        )
    await conn.close()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/users', methods=['POST'])
async def create_user(request):
    data = request.json
    conn = await get_db_connection()
    try:
        user_id = str(uuid.uuid4())
        await conn.execute(SQL_INSERT_USER, user_id, data['username'], data['email'])
        return json({'user_id': user_id}, status=201)
    except asyncpg.UniqueViolationError:
        return json({'error': ERROR_USERNAME_OR_EMAIL_EXISTS}, status=400)
    finally:
        await conn.close()


@app.route('/comments', methods=['POST'])
async def create_comment(request):
    data = request.json
    conn = await get_db_connection()
    try:
        comment_id = str(uuid.uuid4())
        await conn.execute(SQL_INSERT_COMMENT, comment_id, data['user_id'], data['content'])
        return json({'comment_id': comment_id}, status=201)
    except asyncpg.ForeignKeyViolationError:
        return json({'error': ERROR_USER_NOT_FOUND}, status=404)
    finally:
        await conn.close()


@app.route('/comments/search', methods=['GET'])
async def search_comments(request):
    search_term = request.args.get('q')
    if not search_term:
        return json({'error': ERROR_SEARCH_TERM_REQUIRED}, status=400)
    conn = await get_db_connection()
    comments = await conn.fetch(SQL_SEARCH_PUBLIC_COMMENTS, build_search_pattern(search_term))
    results = [serialize_comment(record) for record in comments]
    await conn.close()
    return json({'comments': results})


@app.route('/comments/<comment_id>', methods=['GET'])
async def get_comment(request, comment_id):
    conn = await get_db_connection()
    try:
        comment = await conn.fetchrow(SQL_SELECT_PUBLIC_COMMENT, comment_id)
        if comment:
            return json(serialize_comment(comment))
        return json({'error': ERROR_COMMENT_NOT_FOUND}, status=404)
    finally:
        await conn.close()

# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.add_task(init_db())
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
