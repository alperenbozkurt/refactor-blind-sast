from contextlib import contextmanager

from flask import Flask, request, render_template_string, redirect, url_for
import sqlite3
import html

app = Flask(__name__)

# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------

DATABASE_PATH = 'blog.db'

CREATE_POSTS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS posts\n'
    '                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                 title TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL)'
)

CREATE_COMMENTS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS comments\n'
    '                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                 post_id INTEGER NOT NULL,\n'
    '                 author TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL,\n'
    '                 FOREIGN KEY(post_id) REFERENCES posts(id))'
)

SELECT_POST_TITLES_SQL = 'SELECT id, title FROM posts'
INSERT_POST_SQL = 'INSERT INTO posts (title, content) VALUES (?, ?)'
SELECT_POST_SQL = 'SELECT title, content FROM posts WHERE id = ?'
INSERT_COMMENT_SQL = (
    'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)'
)
SELECT_COMMENTS_SQL = 'SELECT author, content FROM comments WHERE post_id = ?'

# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

INDEX_TEMPLATE = """
        <h1>Blog Posts</h1>
        <ul>
            {% for post in posts %}
                <li><a href="/post/{{ post[0] }}">{{ post[1] }}</a></li>
            {% endfor %}
        </ul>
        <a href="/create">Create New Post</a>
    """

CREATE_POST_TEMPLATE = """
        <h1>Create New Post</h1>
        <form method="POST">
            Title: <input type="text" name="title"><br>
            Content: <textarea name="content"></textarea><br>
            <input type="submit" value="Submit">
        </form>
    """

VIEW_POST_TEMPLATE = """
        <h1>{{ post[0] }}</h1>
        <p>{{ post[1] }}</p>
        
        <h2>Comments</h2>
        <ul>
            {% for comment in comments %}
                <li>
                    <strong>{{ comment[0] }}:</strong>
                    <div>{{ comment[1] }}</div>  <!-- Removed | safe filter -->
                </li>
            {% endfor %}
        </ul>
        
        <h2>Add Comment</h2>
        <form method="POST">
            Name: <input type="text" name="author"><br>
            Comment: <textarea name="comment"></textarea><br>
            <input type="submit" value="Submit">
        </form>
        
        <a href="/">Back to Home</a>
    """

# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------


@contextmanager
def _connection():
    """Open a connection to the blog database and always close it."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _fetch_post_titles():
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_POST_TITLES_SQL)
        return cursor.fetchall()


def _insert_post(title, content):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(INSERT_POST_SQL, (title, content))
        conn.commit()


def _insert_comment(cursor, conn, post_id, author, comment):
    cursor.execute(INSERT_COMMENT_SQL, (post_id, author, comment))
    conn.commit()


def _fetch_post(cursor, post_id):
    cursor.execute(SELECT_POST_SQL, (post_id,))
    return cursor.fetchone()


def _fetch_comments(cursor, post_id):
    cursor.execute(SELECT_COMMENTS_SQL, (post_id,))
    return cursor.fetchall()


def init_db():
    with _connection() as conn:
        c = conn.cursor()
        c.execute(CREATE_POSTS_TABLE_SQL)
        c.execute(CREATE_COMMENTS_TABLE_SQL)
        conn.commit()


init_db()

# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.route('/')
def index():
    posts = _fetch_post_titles()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        _insert_post(title, content)
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    with _connection() as conn:
        c = conn.cursor()
        if request.method == 'POST':
            author = html.escape(request.form['author'])
            comment = html.escape(request.form['comment'])
            _insert_comment(c, conn, post_id, author, comment)
        post = _fetch_post(c, post_id)
        comments = _fetch_comments(c, post_id)
    return render_template_string(VIEW_POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=False)
