"""A minimal Quart-based blog application backed by SQLite."""

import html
import secrets
import sqlite3
import uuid
from datetime import datetime

from markupsafe import escape
from quart import Quart, redirect, render_template_string, request, url_for

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE_PATH = 'blog.db'
DEBUG_MODE = False

CREATE_POSTS_TABLE = (
    'CREATE TABLE IF NOT EXISTS posts\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 title TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL,\n'
    '                 created_at TEXT NOT NULL)'
)
CREATE_COMMENTS_TABLE = (
    'CREATE TABLE IF NOT EXISTS comments\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 post_id TEXT NOT NULL,\n'
    '                 author TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL,\n'
    '                 created_at TEXT NOT NULL,\n'
    '                 FOREIGN KEY(post_id) REFERENCES posts(id))'
)

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

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'",
}

INDEX_TEMPLATE = '''
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
    '''

NEW_POST_TEMPLATE = '''
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
    '''

POST_TEMPLATE = '''
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
    '''


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class BlogConfig:
    """Configuration values for the blog application."""

    def __init__(self, database_path=DATABASE_PATH, debug=DEBUG_MODE):
        self.database_path = database_path
        self.debug = debug
        self.secret_key = secrets.token_urlsafe(32)


config = BlogConfig()

app = Quart(__name__)
app.secret_key = config.secret_key


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db():
    """Create the database tables if they do not already exist."""
    conn = sqlite3.connect(config.database_path)
    c = conn.cursor()
    c.execute(CREATE_POSTS_TABLE)
    c.execute(CREATE_COMMENTS_TABLE)
    conn.commit()
    conn.close()


init_db()


async def get_db_connection():
    """Open a new database connection with row access by column name."""
    conn = sqlite3.connect(config.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def _new_id():
    """Return a new random identifier."""
    return str(uuid.uuid4())


def _current_timestamp():
    """Return the current time as an ISO 8601 string."""
    return datetime.now().isoformat()


async def _create_post(title, content):
    """Insert a new post and return its generated id."""
    post_id = _new_id()
    conn = await get_db_connection()
    await conn.execute(
        INSERT_POST, (post_id, title, content, _current_timestamp()))
    await conn.commit()
    await conn.close()
    return post_id


async def _create_comment(conn, post_id, author, content):
    """Insert a new comment for the given post."""
    await conn.execute(
        INSERT_COMMENT,
        (_new_id(), post_id, author, content, _current_timestamp()))
    await conn.commit()


async def _fetch_recent_posts(conn):
    """Return all posts, newest first."""
    return await conn.execute_fetchall(SELECT_RECENT_POSTS)


async def _fetch_post(conn, post_id):
    """Return the post with the given id, or None if it does not exist."""
    return await conn.execute_fetchone(SELECT_POST_BY_ID, (post_id,))


async def _fetch_comments(conn, post_id):
    """Return all comments for the given post, newest first."""
    return await conn.execute_fetchall(SELECT_COMMENTS_FOR_POST, (post_id,))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
async def index():
    """Show the list of recent posts."""
    conn = await get_db_connection()
    posts = await _fetch_recent_posts(conn)
    await conn.close()
    return await render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/post/new', methods=['GET', 'POST'])
async def new_post():
    """Display the new-post form and handle its submission."""
    if request.method == 'POST':
        form = await request.form
        post_id = await _create_post(
            escape(form['title']), escape(form['content']))
        return redirect(url_for('view_post', post_id=post_id))
    return await render_template_string(NEW_POST_TEMPLATE)


@app.route('/post/<post_id>', methods=['GET', 'POST'])
async def view_post(post_id):
    """Show a post with its comments and handle comment submissions."""
    conn = await get_db_connection()
    if request.method == 'POST':
        form = await request.form
        await _create_comment(
            conn, post_id, escape(form['author']), escape(form['content']))
        return redirect(url_for('view_post', post_id=post_id))
    post = await _fetch_post(conn, post_id)
    comments = await _fetch_comments(conn, post_id)
    await conn.close()
    if not post:
        return ('Post not found', 404)
    return await render_template_string(
        POST_TEMPLATE, post=post, comments=comments)


@app.after_request
async def add_security_headers(response):
    """Add security headers to every response."""
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


if __name__ == '__main__':
    app.run(debug=config.debug)
