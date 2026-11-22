import datetime
import uuid

import asyncpg
from sanic import Sanic, response
from sanic.response import json

app = Sanic('CommentSystem')

DB_CONFIG = {
    'user': 'postgres',
    'password': 'password',
    'database': 'comments_db',
    'host': 'localhost',
}

CREATE_USERS_TABLE = '''
    CREATE TABLE IF NOT EXISTS users (
        user_id UUID PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )
'''

CREATE_COMMENTS_TABLE = '''
    CREATE TABLE IF NOT EXISTS comments (
        comment_id UUID PRIMARY KEY,
        user_id UUID REFERENCES users(user_id),
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        is_public BOOLEAN DEFAULT TRUE
    )
'''

INSERT_USER = (
    'INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)'
)

INSERT_COMMENT = (
    'INSERT INTO comments (comment_id, user_id, content) VALUES ($1, $2, $3)'
)

SEARCH_PUBLIC_COMMENTS = '''
    SELECT c.comment_id, u.username, c.content, c.created_at
    FROM comments c
    JOIN users u ON c.user_id = u.user_id
    WHERE c.content LIKE $1
    AND c.is_public = true
    ORDER BY c.created_at DESC
'''

GET_PUBLIC_COMMENT = (
    'SELECT c.comment_id, u.username, c.content, c.created_at '
    'FROM comments c '
    'JOIN users u ON c.user_id = u.user_id '
    'WHERE c.comment_id = $1 AND c.is_public = true'
)


async def init_db():
    conn = await asyncpg.connect(**DB_CONFIG)
    await conn.execute(CREATE_USERS_TABLE)
    await conn.execute(CREATE_COMMENTS_TABLE)

    user_count = await conn.fetchval('SELECT COUNT(*) FROM users')
    if user_count == 0:
        await conn.execute(
            INSERT_USER,
            str(uuid.uuid4()),
            'admin',
            'admin@example.com',
        )

    await conn.close()


@app.route('/users', methods=['POST'])
async def create_user(request):
    data = request.json
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        user_id = str(uuid.uuid4())
        await conn.execute(
            INSERT_USER,
            user_id,
            data['username'],
            data['email'],
        )
        return json({'user_id': user_id}, status=201)
    except asyncpg.UniqueViolationError:
        return json({'error': 'Username or email already exists'}, status=400)
    finally:
        await conn.close()


@app.route('/comments', methods=['POST'])
async def create_comment(request):
    data = request.json
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        comment_id = str(uuid.uuid4())
        await conn.execute(
            INSERT_COMMENT,
            comment_id,
            data['user_id'],
            data['content'],
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

    conn = await asyncpg.connect(**DB_CONFIG)
    search_pattern = f'%{search_term}%'
    comments = await conn.fetch(SEARCH_PUBLIC_COMMENTS, search_pattern)

    results = [
        {
            'comment_id': record['comment_id'],
            'username': record['username'],
            'content': record['content'],
            'created_at': record['created_at'].isoformat(),
        }
        for record in comments
    ]

    await conn.close()
    return json({'comments': results})


@app.route('/comments/<comment_id>', methods=['GET'])
async def get_comment(request, comment_id):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        comment = await conn.fetchrow(GET_PUBLIC_COMMENT, comment_id)
        if comment:
            return json({
                'comment_id': comment['comment_id'],
                'username': comment['username'],
                'content': comment['content'],
                'created_at': comment['created_at'].isoformat(),
            })
        return json({'error': 'Comment not found'}, status=404)
    finally:
        await conn.close()


if __name__ == '__main__':
    app.add_task(init_db())
    app.run(host='0.0.0.0', port=8000, debug=True)
