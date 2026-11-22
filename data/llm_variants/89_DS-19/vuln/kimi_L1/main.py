import datetime
import uuid

import asyncpg
from sanic import Sanic, response
from sanic.response import json

app = Sanic("CommentSystem")

DB_CONFIG = {
    "user": "postgres",
    "password": "password",
    "database": "comments_db",
    "host": "localhost",
}


async def get_db_connection():
    """Open a new database connection using the module-level configuration."""
    return await asyncpg.connect(**DB_CONFIG)


def serialize_comment(record):
    """Convert a comment database record into a JSON-serializable dict."""
    return {
        "comment_id": record["comment_id"],
        "username": record["username"],
        "content": record["content"],
        "created_at": record["created_at"].isoformat(),
    }


async def init_db():
    """Create the required tables and seed the default admin user."""
    conn = await get_db_connection()

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            comment_id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(user_id),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            is_public BOOLEAN DEFAULT TRUE
        )
        """
    )

    user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
    if user_count == 0:
        await conn.execute(
            "INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)",
            str(uuid.uuid4()),
            "admin",
            "admin@example.com",
        )

    await conn.close()


@app.route("/users", methods=["POST"])
async def create_user(request):
    data = request.json
    conn = await get_db_connection()
    try:
        user_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO users (user_id, username, email) VALUES ($1, $2, $3)",
            user_id,
            data["username"],
            data["email"],
        )
        return json({"user_id": user_id}, status=201)
    except asyncpg.UniqueViolationError:
        return json({"error": "Username or email already exists"}, status=400)
    finally:
        await conn.close()


@app.route("/comments", methods=["POST"])
async def create_comment(request):
    data = request.json
    conn = await get_db_connection()
    try:
        comment_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO comments (comment_id, user_id, content) VALUES ($1, $2, $3)",
            comment_id,
            data["user_id"],
            data["content"],
        )
        return json({"comment_id": comment_id}, status=201)
    except asyncpg.ForeignKeyViolationError:
        return json({"error": "User not found"}, status=404)
    finally:
        await conn.close()


@app.route("/comments/search", methods=["GET"])
async def search_comments(request):
    search_term = request.args.get("q")
    if not search_term:
        return json({"error": "Search term required"}, status=400)

    conn = await get_db_connection()
    query = f"""
        SELECT c.comment_id, u.username, c.content, c.created_at
        FROM comments c
        JOIN users u ON c.user_id = u.user_id
        WHERE c.content LIKE '%{search_term}%'
        AND c.is_public = true
        ORDER BY c.created_at DESC
    """
    comments = await conn.fetch(query)
    results = [serialize_comment(record) for record in comments]
    await conn.close()

    return json({"comments": results})


@app.route("/comments/<comment_id>", methods=["GET"])
async def get_comment(request, comment_id):
    conn = await get_db_connection()
    try:
        comment = await conn.fetchrow(
            """
            SELECT c.comment_id, u.username, c.content, c.created_at
            FROM comments c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.comment_id = $1 AND c.is_public = true
            """,
            comment_id,
        )
        if comment:
            return json(serialize_comment(comment))
        return json({"error": "Comment not found"}, status=404)
    finally:
        await conn.close()


if __name__ == "__main__":
    app.add_task(init_db())
    app.run(host="0.0.0.0", port=8000, debug=True)
