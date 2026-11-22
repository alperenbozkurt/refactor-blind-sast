from quart import Quart, request, render_template_string, redirect, url_for
import sqlite3
import uuid
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'blog.db'

_SQL_INDENT = ' ' * 17

CREATE_POSTS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS posts\n'
    + _SQL_INDENT + '(id TEXT PRIMARY KEY,\n'
    + _SQL_INDENT + 'title TEXT NOT NULL,\n'
    + _SQL_INDENT + 'content TEXT NOT NULL,\n'
    + _SQL_INDENT + 'created_at TEXT NOT NULL)'
)

CREATE_COMMENTS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS comments\n'
    + _SQL_INDENT + '(id TEXT PRIMARY KEY,\n'
    + _SQL_INDENT + 'post_id TEXT NOT NULL,\n'
    + _SQL_INDENT + 'author TEXT NOT NULL,\n'
    + _SQL_INDENT + 'content TEXT NOT NULL,\n'
    + _SQL_INDENT + 'created_at TEXT NOT NULL,\n'
    + _SQL_INDENT + 'FOREIGN KEY(post_id) REFERENCES posts(id))'
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

POST_NOT_FOUND_MESSAGE = 'Post not found'
HTTP_NOT_FOUND = 404

# ---------------------------------------------------------------------------
# Templates
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
# Application
# ---------------------------------------------------------------------------

app = Quart(__name__)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _new_id():
    return str(uuid.uuid4())


def _timestamp():
    return datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

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


async def _fetch_post_list(conn):
    return await conn.execute_fetchall(SELECT_POST_LIST_SQL)


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


async def _fetch_post(conn, post_id):
    return await conn.execute_fetchone(SELECT_POST_SQL, (post_id,))


async def _fetch_comments(conn, post_id):
    return await conn.execute_fetchall(SELECT_COMMENTS_SQL, (post_id,))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
async def index():
    conn = await get_db_connection()
    posts = await _fetch_post_list(conn)
    await conn.close()
    return await render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/post/new', methods=['GET', 'POST'])
async def new_post():
    if request.method == 'POST':
        form = await request.form
        post_id = _new_id()
        conn = await get_db_connection()
        await _insert_post(conn, post_id, form['title'], form['content'])
        await conn.close()
        return redirect(url_for('view_post', post_id=post_id))
    return await render_template_string(NEW_POST_TEMPLATE)


@app.route('/post/<post_id>', methods=['GET', 'POST'])
async def view_post(post_id):
    conn = await get_db_connection()
    if request.method == 'POST':
        form = await request.form
        await _insert_comment(conn, post_id, form['author'], form['content'])
        return redirect(url_for('view_post', post_id=post_id))
    post = await _fetch_post(conn, post_id)
    comments = await _fetch_comments(conn, post_id)
    await conn.close()
    if not post:
        return (POST_NOT_FOUND_MESSAGE, HTTP_NOT_FOUND)
    return await render_template_string(
        VIEW_POST_TEMPLATE, post=post, comments=comments
    )


if __name__ == '__main__':
    app.run(debug=True)
