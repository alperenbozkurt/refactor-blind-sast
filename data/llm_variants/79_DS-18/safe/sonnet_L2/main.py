from quart import Quart, request, render_template_string, redirect, url_for
import sqlite3
import uuid
from datetime import datetime
import html
import secrets
from markupsafe import escape


# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------

DATABASE_PATH = 'blog.db'
SECRET_KEY_BYTES = 32

HTTP_NOT_FOUND = 404
POST_NOT_FOUND_MESSAGE = 'Post not found'

SECURITY_HEADERS = (
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('X-XSS-Protection', '1; mode=block'),
    ('Content-Security-Policy', "default-src 'self'"),
)


# --------------------------------------------------------------------------
# SQL statements
# --------------------------------------------------------------------------

CREATE_POSTS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS posts\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 title TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL,\n'
    '                 created_at TEXT NOT NULL)'
)

CREATE_COMMENTS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS comments\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 post_id TEXT NOT NULL,\n'
    '                 author TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL,\n'
    '                 created_at TEXT NOT NULL,\n'
    '                 FOREIGN KEY(post_id) REFERENCES posts(id))'
)

SELECT_POST_LIST_SQL = 'SELECT id, title FROM posts ORDER BY created_at DESC'
INSERT_POST_SQL = (
    'INSERT INTO posts (id, title, content, created_at) VALUES (?, ?, ?, ?)'
)
SELECT_POST_SQL = 'SELECT * FROM posts WHERE id = ?'
SELECT_COMMENTS_SQL = (
    'SELECT * FROM comments WHERE post_id = ? ORDER BY created_at DESC'
)
INSERT_COMMENT_SQL = (
    'INSERT INTO comments (id, post_id, author, content, created_at) '
    'VALUES (?, ?, ?, ?, ?)'
)


# --------------------------------------------------------------------------
# HTML templates
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------

app = Quart(__name__)
app.secret_key = secrets.token_urlsafe(SECRET_KEY_BYTES)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _new_id():
    return str(uuid.uuid4())


def _timestamp():
    return datetime.now().isoformat()


def _post_redirect(post_id):
    return redirect(url_for('view_post', post_id=post_id))


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute(CREATE_POSTS_TABLE_SQL)
    c.execute(CREATE_COMMENTS_TABLE_SQL)
    conn.commit()
    conn.close()


init_db()


async def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------
# Data access helpers
# --------------------------------------------------------------------------

async def _insert_post(conn, post_id, title, content):
    await conn.execute(
        INSERT_POST_SQL, (post_id, title, content, _timestamp())
    )
    await conn.commit()


async def _insert_comment(conn, post_id, author, content):
    await conn.execute(
        INSERT_COMMENT_SQL,
        (_new_id(), post_id, author, content, _timestamp()),
    )
    await conn.commit()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route('/')
async def index():
    conn = await get_db_connection()
    posts = await conn.execute_fetchall(SELECT_POST_LIST_SQL)
    await conn.close()
    return await render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/post/new', methods=['GET', 'POST'])
async def new_post():
    if request.method == 'POST':
        form = await request.form
        post_id = _new_id()
        title = escape(form['title'])
        content = escape(form['content'])
        conn = await get_db_connection()
        await _insert_post(conn, post_id, title, content)
        await conn.close()
        return _post_redirect(post_id)
    return await render_template_string(NEW_POST_TEMPLATE)


@app.route('/post/<post_id>', methods=['GET', 'POST'])
async def view_post(post_id):
    conn = await get_db_connection()
    if request.method == 'POST':
        form = await request.form
        author = escape(form['author'])
        content = escape(form['content'])
        await _insert_comment(conn, post_id, author, content)
        return _post_redirect(post_id)
    post = await conn.execute_fetchone(SELECT_POST_SQL, (post_id,))
    comments = await conn.execute_fetchall(SELECT_COMMENTS_SQL, (post_id,))
    await conn.close()
    if not post:
        return (POST_NOT_FOUND_MESSAGE, HTTP_NOT_FOUND)
    return await render_template_string(
        VIEW_POST_TEMPLATE, post=post, comments=comments
    )


@app.after_request
async def add_security_headers(response):
    for name, value in SECURITY_HEADERS:
        response.headers[name] = value
    return response


if __name__ == '__main__':
    app.run(debug=False)
