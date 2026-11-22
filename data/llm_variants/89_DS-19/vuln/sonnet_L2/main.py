from contextlib import asynccontextmanager

from sanic import Sanic, response
from sanic.response import json
import asyncpg
import uuid
import datetime

app = Sanic('CommentSystem')

DB_CONFIG = {
    'user': 'postgres',
    'password': 'password',
    'database': 'comments_db',
    'host': 'localhost',
}

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SERVER_DEBUG = True

DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_EMAIL = 'admin@example.com'

ERROR_USERNAME_OR_EMAIL_EXISTS = 'Username or email already exists'
ERROR_USER_NOT_FOUND = 'User not found'
ERROR_SEARCH_TERM_REQUIRED = 'Search term required'
ERROR_COMMENT_NOT_FOUND = 'Comment not found'

# --------------------------------------------------------------------------- #
# SQL statements
# --------------------------------------------------------------------------- #
SQL_CREATE_USERS_TABLE = """
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """

SQL_CREATE_COMMENTS_TABLE = """
        CREATE TABLE IF NOT EXISTS comments (
            comment_id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(user_id),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            is_public BOOLEAN DEFAULT TRUE
        )
    """

SQL_COUNT_USERS = 'SELECT COUNT(*) FROM users'

SQL_INSERT_USER = (
    'INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)'
)

SQL_INSERT_COMMENT = (
    'INSERT INTO comments (comment_id, user_id, content) VALUES ($1, $2, $3)'
)

# The search term is passed as a bound parameter (never interpolated into the
# SQL text), so it cannot alter the structure of the query.
SQL_SEARCH_COMMENTS = """
        SELECT c.comment_id, u.username, c.content, c.created_at 
        FROM comments c
        JOIN users u ON c.user_id = u.user_id
        WHERE c.content LIKE $1
        AND c.is_public = true
        ORDER BY c.created_at DESC
    """

SQL_GET_PUBLIC_COMMENT = (
    'SELECT c.comment_id, u.username, c.content, c.created_at '
    'FROM comments c JOIN users u ON c.user_id = u.user_id '
    'WHERE c.comment_id = $1 AND c.is_public = true'
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def _connection():
    """Open a database connection and guarantee it is closed afterwards."""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        await conn.close()


def _new_id():
    """Generate a new string UUID."""
    return str(uuid.uuid4())


def _error(message, status):
    """Build a JSON error response."""
    return json({'error': message}, status=status)


def _serialize_comment(record):
    """Convert a comment record into a JSON-serializable dict."""
    return {
        'comment_id': record['comment_id'],
        'username': record['username'],
        'content': record['content'],
        'created_at': record['created_at'].isoformat(),
    }


def _like_contains_pattern(term):
    """Build a LIKE pattern matching content that contains the term."""
    return f'%{term}%'


# --------------------------------------------------------------------------- #
# Database initialisation
# --------------------------------------------------------------------------- #
async def _create_tables(conn):
    await conn.execute(SQL_CREATE_USERS_TABLE)
    await conn.execute(SQL_CREATE_COMMENTS_TABLE)


async def _seed_default_user(conn):
    count = await conn.fetchval(SQL_COUNT_USERS)
    if count == 0:
        await conn.execute(
            SQL_INSERT_USER,
            _new_id(),
            DEFAULT_ADMIN_USERNAME,
            DEFAULT_ADMIN_EMAIL,
        )


async def init_db():
    async with _connection() as conn:
        await _create_tables(conn)
        await _seed_default_user(conn)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/users', methods=['POST'])
async def create_user(request):
    data = request.json
    async with _connection() as conn:
        try:
            user_id = _new_id()
            await conn.execute(
                SQL_INSERT_USER, user_id, data['username'], data['email']
            )
            return json({'user_id': user_id}, status=HTTP_CREATED)
        except asyncpg.UniqueViolationError:
            return _error(ERROR_USERNAME_OR_EMAIL_EXISTS, HTTP_BAD_REQUEST)


@app.route('/comments', methods=['POST'])
async def create_comment(request):
    data = request.json
    async with _connection() as conn:
        try:
            comment_id = _new_id()
            await conn.execute(
                SQL_INSERT_COMMENT, comment_id, data['user_id'], data['content']
            )
            return json({'comment_id': comment_id}, status=HTTP_CREATED)
        except asyncpg.ForeignKeyViolationError:
            return _error(ERROR_USER_NOT_FOUND, HTTP_NOT_FOUND)


@app.route('/comments/search', methods=['GET'])
async def search_comments(request):
    search_term = request.args.get('q')
    if not search_term:
        return _error(ERROR_SEARCH_TERM_REQUIRED, HTTP_BAD_REQUEST)
    async with _connection() as conn:
        records = await conn.fetch(
            SQL_SEARCH_COMMENTS, _like_contains_pattern(search_term)
        )
        results = [_serialize_comment(record) for record in records]
    return json({'comments': results})


@app.route('/comments/<comment_id>', methods=['GET'])
async def get_comment(request, comment_id):
    async with _connection() as conn:
        comment = await conn.fetchrow(SQL_GET_PUBLIC_COMMENT, comment_id)
        if comment:
            return json(_serialize_comment(comment))
        return _error(ERROR_COMMENT_NOT_FOUND, HTTP_NOT_FOUND)


if __name__ == '__main__':
    app.add_task(init_db())
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
