"""A small Flask blog application with posts and comments.

This module preserves the original public interface (``app``, ``init_db``
and the route handlers) while organising the implementation into named
constants and small, single-purpose database helper functions.
"""

import html
import sqlite3
from contextlib import contextmanager

from flask import Flask, redirect, render_template_string, request, url_for

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'blog.db'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_POSTS_TABLE_SQL = 'CREATE TABLE IF NOT EXISTS posts\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 title TEXT NOT NULL,\n                 content TEXT NOT NULL)'
CREATE_COMMENTS_TABLE_SQL = 'CREATE TABLE IF NOT EXISTS comments\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 post_id INTEGER NOT NULL,\n                 author TEXT NOT NULL,\n                 content TEXT NOT NULL,\n                 FOREIGN KEY(post_id) REFERENCES posts(id))'

SELECT_ALL_POSTS_SQL = 'SELECT id, title FROM posts'
INSERT_POST_SQL = 'INSERT INTO posts (title, content) VALUES (?, ?)'
SELECT_POST_SQL = 'SELECT title, content FROM posts WHERE id = ?'
INSERT_COMMENT_SQL = 'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)'
SELECT_COMMENTS_SQL = 'SELECT author, content FROM comments WHERE post_id = ?'

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = '\n        <h1>Blog Posts</h1>\n        <ul>\n            {% for post in posts %}\n                <li><a href="/post/{{ post[0] }}">{{ post[1] }}</a></li>\n            {% endfor %}\n        </ul>\n        <a href="/create">Create New Post</a>\n    '
CREATE_POST_TEMPLATE = '\n        <h1>Create New Post</h1>\n        <form method="POST">\n            Title: <input type="text" name="title"><br>\n            Content: <textarea name="content"></textarea><br>\n            <input type="submit" value="Submit">\n        </form>\n    '
VIEW_POST_TEMPLATE = '\n        <h1>{{ post[0] }}</h1>\n        <p>{{ post[1] }}</p>\n        \n        <h2>Comments</h2>\n        <ul>\n            {% for comment in comments %}\n                <li>\n                    <strong>{{ comment[0] }}:</strong>\n                    <div>{{ comment[1] }}</div>  <!-- Removed | safe filter -->\n                </li>\n            {% endfor %}\n        </ul>\n        \n        <h2>Add Comment</h2>\n        <form method="POST">\n            Name: <input type="text" name="author"><br>\n            Comment: <textarea name="comment"></textarea><br>\n            <input type="submit" value="Submit">\n        </form>\n        \n        <a href="/">Back to Home</a>\n    '

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def _db_connection():
    """Yield an open SQLite connection and guarantee it is closed."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_POSTS_TABLE_SQL)
        cursor.execute(CREATE_COMMENTS_TABLE_SQL)
        conn.commit()


def _fetch_all_posts():
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_POSTS_SQL)
        return cursor.fetchall()


def _insert_post(title, content):
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(INSERT_POST_SQL, (title, content))
        conn.commit()


def _fetch_post(post_id):
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_POST_SQL, (post_id,))
        return cursor.fetchone()


def _fetch_comments(post_id):
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_COMMENTS_SQL, (post_id,))
        return cursor.fetchall()


def _insert_comment(post_id, author, content):
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(INSERT_COMMENT_SQL, (post_id, author, content))
        conn.commit()


init_db()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    posts = _fetch_all_posts()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        _insert_post(request.form['title'], request.form['content'])
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    if request.method == 'POST':
        author = html.escape(request.form['author'])
        comment = html.escape(request.form['comment'])
        _insert_comment(post_id, author, comment)
    post = _fetch_post(post_id)
    comments = _fetch_comments(post_id)
    return render_template_string(VIEW_POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=False)
