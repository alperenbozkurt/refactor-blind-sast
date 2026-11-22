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

CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        user_id UUID PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )
"""

CREATE_COMMENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS comments (
        comment_id UUID PRIMARY KEY,
        user_id UUID REFERENCES users(user_id),
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        is_public BOOLEAN DEFAULT TRUE
    )
"""

INSERT_USER = 'INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)'
INSERT_COMMENT = 'INSERT INTO comments (comment_id, user_id, content) VALUES ($1, $2, $3)'

SEARCH_COMMENTS = """
    SELECT c.comment_id, u.username, c.content, c.created_at
    FROM comments c
    JOIN users u ON c.user_id = u.user_id
    WHERE c.content LIKE '%' || $1 || '%'
    AND c.is_public = true
    ORDER BY c.created_at DESC
"""

SELECT_PUBLIC_COMMENT = (
    'SELECT c.comment_id, u.username, c.content, c.created_at '
    'FROM comments c JOIN users u ON c.user_id = u.user_id '
    'WHERE c.comment_id = $1 AND c.is_public = true'
)


@asynccontextmanager
async def db_connection():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        await conn.close()


def serialize_comment(record):
    return {
        'comment_id': record['comment_id'],
        'username': record['username'],
        'content': record['content'],
        'created_at': record['created_at'].isoformat(),
    }


async def init_db():
    async with db_connection() as conn:
        await conn.execute(CREATE_USERS_TABLE)
        await conn.execute(CREATE_COMMENTS_TABLE)
        count = await conn.fetchval('SELECT COUNT(*) FROM users')
        if count == 0:
            await conn.execute(
                INSERT_USER, str(uuid.uuid4()), 'admin', 'admin@example.com'
            )


@app.route('/users', methods=['POST'])
async def create_user(request):
    data = request.json
    async with db_connection() as conn:
        try:
            user_id = str(uuid.uuid4())
            await conn.execute(INSERT_USER, user_id, data['username'], data['email'])
            return json({'user_id': user_id}, status=201)
        except asyncpg.UniqueViolationError:
            return json({'error': 'Username or email already exists'}, status=400)


@app.route('/comments', methods=['POST'])
async def create_comment(request):
    data = request.json
    async with db_connection() as conn:
        try:
            comment_id = str(uuid.uuid4())
            await conn.execute(
                INSERT_COMMENT, comment_id, data['user_id'], data['content']
            )
            return json({'comment_id': comment_id}, status=201)
        except asyncpg.ForeignKeyViolationError:
            return json({'error': 'User not found'}, status=404)


@app.route('/comments/search', methods=['GET'])
async def search_comments(request):
    search_term = request.args.get('q')
    if not search_term:
        return json({'error': 'Search term required'}, status=400)
    async with db_connection() as conn:
        records = await conn.fetch(SEARCH_COMMENTS, search_term)
    return json({'comments': [serialize_comment(record) for record in records]})


@app.route('/comments/<comment_id>', methods=['GET'])
async def get_comment(request, comment_id):
    async with db_connection() as conn:
        comment = await conn.fetchrow(SELECT_PUBLIC_COMMENT, comment_id)
        if comment:
            return json(serialize_comment(comment))
        return json({'error': 'Comment not found'}, status=404)


if __name__ == '__main__':
    app.add_task(init_db())
    app.run(host='0.0.0.0', port=8000, debug=True)
