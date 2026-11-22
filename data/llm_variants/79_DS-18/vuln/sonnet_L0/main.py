import sqlite3
import uuid
from datetime import datetime

from quart import Quart, request, render_template_string, redirect, url_for

app = Quart(__name__)

DB_PATH = 'blog.db'

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


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(CREATE_POSTS_TABLE)
    c.execute(CREATE_COMMENTS_TABLE)
    conn.commit()
    conn.close()


init_db()


async def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _new_id():
    return str(uuid.uuid4())


def _timestamp():
    return datetime.now().isoformat()


@app.route('/')
async def index():
    conn = await get_db_connection()
    posts = await conn.execute_fetchall(
        'SELECT id, title FROM posts ORDER BY created_at DESC'
    )
    await conn.close()
    return await render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/post/new', methods=['GET', 'POST'])
async def new_post():
    if request.method == 'POST':
        form = await request.form
        post_id = _new_id()
        conn = await get_db_connection()
        await conn.execute(
            'INSERT INTO posts (id, title, content, created_at) VALUES (?, ?, ?, ?)',
            (post_id, form['title'], form['content'], _timestamp()),
        )
        await conn.commit()
        await conn.close()
        return redirect(url_for('view_post', post_id=post_id))
    return await render_template_string(NEW_POST_TEMPLATE)


@app.route('/post/<post_id>', methods=['GET', 'POST'])
async def view_post(post_id):
    conn = await get_db_connection()
    if request.method == 'POST':
        form = await request.form
        await conn.execute(
            'INSERT INTO comments (id, post_id, author, content, created_at) VALUES (?, ?, ?, ?, ?)',
            (_new_id(), post_id, form['author'], form['content'], _timestamp()),
        )
        await conn.commit()
        return redirect(url_for('view_post', post_id=post_id))
    post = await conn.execute_fetchone(
        'SELECT * FROM posts WHERE id = ?', (post_id,)
    )
    comments = await conn.execute_fetchall(
        'SELECT * FROM comments WHERE post_id = ? ORDER BY created_at DESC',
        (post_id,),
    )
    await conn.close()
    if not post:
        return ('Post not found', 404)
    return await render_template_string(
        VIEW_POST_TEMPLATE, post=post, comments=comments
    )


if __name__ == '__main__':
    app.run(debug=True)
