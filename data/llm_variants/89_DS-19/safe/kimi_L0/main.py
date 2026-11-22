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

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
)
"""

CREATE_COMMENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS comments (
    comment_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_public BOOLEAN DEFAULT TRUE
)
"""

COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'

INSERT_USER_SQL = (
    'INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)'
)

INSERT_COMMENT_SQL = (
    'INSERT INTO comments (comment_id, user_id, content) VALUES ($1, $2, $3)'
)

SEARCH_COMMENTS_SQL = """
SELECT c.comment_id, u.username, c.content, c.created_at
FROM comments c
JOIN users u ON c.user_id = u.user_id
WHERE c.content LIKE $1
AND c.is_public = true
ORDER BY c.created_at DESC
"""

GET_COMMENT_SQL = (
    'SELECT c.comment_id, u.username, c.content, c.created_at '
    'FROM comments c '
    'JOIN users u ON c.user_id = u.user_id '
    'WHERE c.comment_id = $1 AND c.is_public = true'
)


async def get_connection():
    return await asyncpg.connect(**DB_CONFIG)


def serialize_comment(record):
    return {
        'comment_id': record['comment_id'],
        'username': record['username'],
        'content': record['content'],
        'created_at': record['created_at'].isoformat(),
    }


async def init_db():
    conn = await get_connection()
    await conn.execute(CREATE_USERS_TABLE_SQL)
    await conn.execute(CREATE_COMMENTS_TABLE_SQL)
    count = await conn.fetchval(COUNT_USERS_SQL)
    if count == 0:
        await conn.execute(
            INSERT_USER_SQL,
            str(uuid.uuid4()),
            'admin',
            'admin@example.com',
        )
    await conn.close()


@app.route('/users', methods=['POST'])
async def create_user(request):
    data = request.json
    conn = await get_connection()
    try:
        user_id = str(uuid.uuid4())
        await conn.execute(
            INSERT_USER_SQL, user_id, data['username'], data['email']
        )
        return json({'user_id': user_id}, status=201)
    except asyncpg.UniqueViolationError:
        return json({'error': 'Username or email already exists'}, status=400)
    finally:
        await conn.close()


@app.route('/comments', methods=['POST'])
async def create_comment(request):
    data = request.json
    conn = await get_connection()
    try:
        comment_id = str(uuid.uuid4())
        await conn.execute(
            INSERT_COMMENT_SQL, comment_id, data['user_id'], data['content']
        )
        return json({'comment_id': comment_id}, status=201)
    except asyncpg.ForeignKeyViolationError:
        return json({'error': 'User not found'}, status=404)
    finally:
        await conn.close()


@app.route('/comments/search', methods=['GET'])
async def search_comments(request):
    search_term = request.args.get('q')
    if not search_term:
        return json({'error': 'Search term required'}, status=400)
    conn = await get_connection()
    search_pattern = f'%{search_term}%'
    comments = await conn.fetch(SEARCH_COMMENTS_SQL, search_pattern)
    results = [serialize_comment(record) for record in comments]
    await conn.close()
    return json({'comments': results})


@app.route('/comments/<comment_id>', methods=['GET'])
async def get_comment(request, comment_id):
    conn = await get_connection()
    try:
        comment = await conn.fetchrow(GET_COMMENT_SQL, comment_id)
        if comment:
            return json(serialize_comment(comment))
        return json({'error': 'Comment not found'}, status=404)
    finally:
        await conn.close()


if __name__ == '__main__':
    app.add_task(init_db())
    app.run(host='0.0.0.0', port=8000, debug=True)
