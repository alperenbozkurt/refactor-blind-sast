"""A minimal Quart-based blog application with posts and comments."""

import html
import secrets
import sqlite3
import uuid
from datetime import datetime

from markupsafe import escape
from quart import Quart, redirect, render_template_string, request, url_for

app = Quart(__name__)
app.secret_key = secrets.token_urlsafe(32)

DATABASE = 'blog.db'

CREATE_POSTS_TABLE_SQL = """CREATE TABLE IF NOT EXISTS posts
                 (id TEXT PRIMARY KEY,
                 title TEXT NOT NULL,
                 content TEXT NOT NULL,
                 created_at TEXT NOT NULL)"""

CREATE_COMMENTS_TABLE_SQL = """CREATE TABLE IF NOT EXISTS comments
                 (id TEXT PRIMARY KEY,
                 post_id TEXT NOT NULL,
                 author TEXT NOT NULL,
                 content TEXT NOT NULL,
                 created_at TEXT NOT NULL,
                 FOREIGN KEY(post_id) REFERENCES posts(id))"""

LIST_POSTS_SQL = 'SELECT id, title FROM posts ORDER BY created_at DESC'
INSERT_POST_SQL = (
    'INSERT INTO posts (id, title, content, created_at) VALUES (?, ?, ?, ?)'
)
SELECT_POST_SQL = 'SELECT * FROM posts WHERE id = ?'
INSERT_COMMENT_SQL = (
    'INSERT INTO comments (id, post_id, author, content, created_at) '
    'VALUES (?, ?, ?, ?, ?)'
)
SELECT_COMMENTS_SQL = (
    'SELECT * FROM comments WHERE post_id = ? ORDER BY created_at DESC'
)

INDEX_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Blog</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .post { border-bottom: 1px solid #eee; padding: 15px 0; }
            </style>
        </head>
        <body>
            <h1>Welcome to My Blog</h1>
            <a href="{{ url_for('new_post') }}">Create New Post</a>
            
            <h2>Recent Posts</h2>
            {% for post in posts %}
                <div class="post">
                    <h3><a href="{{ url_for('view_post', post_id=post['id']) }}">{{ post['title'] }}</a></h3>
                </div>
            {% endfor %}
        </body>
        </html>
    """

NEW_POST_TEMPLATE = """
        <h1>Create New Post</h1>
        <form method="POST">
            <p>
                <label>Title:</label><br>
                <input type="text" name="title" required maxlength="200">
            </p>
            <p>
                <label>Content:</label><br>
                <textarea name="content" rows="10" required maxlength="5000"></textarea>
            </p>
            <button type="submit">Publish</button>
        </form>
    """

VIEW_POST_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ post['title'] }}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .comment { border: 1px solid #eee; padding: 10px; margin: 10px 0; }
                .comment-meta { font-size: 0.8em; color: #666; }
            </style>
        </head>
        <body>
            <h1>{{ post['title'] }}</h1>
            <p>{{ post['content'] }}</p>
            <p><small>Posted on {{ post['created_at'] }}</small></p>
            
            <h2>Comments</h2>
            {% for comment in comments %}
                <div class="comment">
                    <div class="comment-meta">
                        Posted by {{ comment['author'] }} on {{ comment['created_at'] }}
                    </div>
                    <div class="comment-content">
                        {{ comment['content'] }}  <!-- Removed | safe filter -->
                    </div>
                </div>
            {% endfor %}
            
            <h3>Add a Comment</h3>
            <form method="POST">
                <p>
                    <label>Your Name:</label><br>
                    <input type="text" name="author" required maxlength="100">
                </p>
                <p>
                    <label>Your Comment:</label><br>
                    <textarea name="content" rows="4" required maxlength="1000"></textarea>
                </p>
                <button type="submit">Submit Comment</button>
            </form>
            
            <p><a href="{{ url_for('index') }}">Back to all posts</a></p>
        </body>
        </html>
    """

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'",
}


def init_db():
    """Create the posts and comments tables if they do not exist."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_POSTS_TABLE_SQL)
    cursor.execute(CREATE_COMMENTS_TABLE_SQL)
    conn.commit()
    conn.close()


init_db()


async def get_db_connection():
    """Open a connection to the blog database with named row access."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
async def index():
    """Render the landing page with the most recent posts."""
    conn = await get_db_connection()
    posts = await conn.execute_fetchall(LIST_POSTS_SQL)
    await conn.close()
    return await render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/post/new', methods=['GET', 'POST'])
async def new_post():
    """Create a new post on POST, otherwise render the new-post form."""
    if request.method == 'POST':
        form = await request.form
        post_id = str(uuid.uuid4())
        title = escape(form['title'])
        content = escape(form['content'])
        conn = await get_db_connection()
        await conn.execute(
            INSERT_POST_SQL,
            (post_id, title, content, datetime.now().isoformat()),
        )
        await conn.commit()
        await conn.close()
        return redirect(url_for('view_post', post_id=post_id))
    return await render_template_string(NEW_POST_TEMPLATE)


@app.route('/post/<post_id>', methods=['GET', 'POST'])
async def view_post(post_id):
    """Show a post and its comments; accept new comments via POST."""
    conn = await get_db_connection()
    if request.method == 'POST':
        form = await request.form
        author = escape(form['author'])
        content = escape(form['content'])
        await conn.execute(
            INSERT_COMMENT_SQL,
            (str(uuid.uuid4()), post_id, author, content,
             datetime.now().isoformat()),
        )
        await conn.commit()
        return redirect(url_for('view_post', post_id=post_id))
    post = await conn.execute_fetchone(SELECT_POST_SQL, (post_id,))
    comments = await conn.execute_fetchall(SELECT_COMMENTS_SQL, (post_id,))
    await conn.close()
    if not post:
        return ('Post not found', 404)
    return await render_template_string(
        VIEW_POST_TEMPLATE, post=post, comments=comments
    )


@app.after_request
async def add_security_headers(response):
    """Attach security-related headers to every outgoing response."""
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


if __name__ == '__main__':
    app.run(debug=False)
