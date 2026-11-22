"""A minimal Quart blog application backed by a SQLite database."""

import sqlite3
import uuid
from datetime import datetime

from quart import Quart, redirect, render_template_string, request, url_for

DATABASE_PATH = 'blog.db'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_POSTS_TABLE = """
    CREATE TABLE IF NOT EXISTS posts
        (id TEXT PRIMARY KEY,
         title TEXT NOT NULL,
         content TEXT NOT NULL,
         created_at TEXT NOT NULL)
"""

CREATE_COMMENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS comments
        (id TEXT PRIMARY KEY,
         post_id TEXT NOT NULL,
         author TEXT NOT NULL,
         content TEXT NOT NULL,
         created_at TEXT NOT NULL,
         FOREIGN KEY(post_id) REFERENCES posts(id))
"""

SELECT_RECENT_POSTS = 'SELECT id, title FROM posts ORDER BY created_at DESC'
SELECT_POST_BY_ID = 'SELECT * FROM posts WHERE id = ?'
SELECT_COMMENTS_FOR_POST = (
    'SELECT * FROM comments WHERE post_id = ? ORDER BY created_at DESC'
)
INSERT_POST = (
    'INSERT INTO posts (id, title, content, created_at) VALUES (?, ?, ?, ?)'
)
INSERT_COMMENT = (
    'INSERT INTO comments (id, post_id, author, content, created_at) '
    'VALUES (?, ?, ?, ?, ?)'
)

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Blog</title>
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
                <input type="text" name="title" required>
            </p>
            <p>
                <label>Content:</label><br>
                <textarea name="content" rows="10" required></textarea>
            </p>
            <button type="submit">Publish</button>
        </form>
    """

VIEW_POST_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ post['title'] }}</title>
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
                        {{ comment['content'] | safe }}
                    </div>
                </div>
            {% endfor %}
            
            <h3>Add a Comment</h3>
            <form method="POST">
                <p>
                    <label>Your Name:</label><br>
                    <input type="text" name="author" required>
                </p>
                <p>
                    <label>Your Comment:</label><br>
                    <textarea name="content" rows="4" required></textarea>
                </p>
                <button type="submit">Submit Comment</button>
            </form>
            
            <p><a href="{{ url_for('index') }}">Back to all posts</a></p>
        </body>
        </html>
    """

# ---------------------------------------------------------------------------
# Application and database setup
# ---------------------------------------------------------------------------

app = Quart(__name__)


def init_db():
    """Create the posts and comments tables if they do not already exist."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_POSTS_TABLE)
    cursor.execute(CREATE_COMMENTS_TABLE)
    conn.commit()
    conn.close()


init_db()


async def get_db_connection():
    """Return a SQLite connection whose rows are accessible by column name."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
async def index():
    """Show the list of all posts, newest first."""
    conn = await get_db_connection()
    posts = await conn.execute_fetchall(SELECT_RECENT_POSTS)
    await conn.close()
    return await render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/post/new', methods=['GET', 'POST'])
async def new_post():
    """Render the new-post form and store submitted posts."""
    if request.method == 'POST':
        form = await request.form
        post_id = str(uuid.uuid4())
        conn = await get_db_connection()
        await conn.execute(
            INSERT_POST,
            (post_id, form['title'], form['content'], datetime.now().isoformat()),
        )
        await conn.commit()
        await conn.close()
        return redirect(url_for('view_post', post_id=post_id))
    return await render_template_string(NEW_POST_TEMPLATE)


@app.route('/post/<post_id>', methods=['GET', 'POST'])
async def view_post(post_id):
    """Display a single post with its comments and accept new comments."""
    conn = await get_db_connection()
    if request.method == 'POST':
        form = await request.form
        await conn.execute(
            INSERT_COMMENT,
            (
                str(uuid.uuid4()),
                post_id,
                form['author'],
                form['content'],
                datetime.now().isoformat(),
            ),
        )
        await conn.commit()
        return redirect(url_for('view_post', post_id=post_id))
    post = await conn.execute_fetchone(SELECT_POST_BY_ID, (post_id,))
    comments = await conn.execute_fetchall(SELECT_COMMENTS_FOR_POST, (post_id,))
    await conn.close()
    if not post:
        return ('Post not found', 404)
    return await render_template_string(
        VIEW_POST_TEMPLATE, post=post, comments=comments
    )


if __name__ == '__main__':
    app.run(debug=True)
