"""Minimal Flask blog with posts and comments, backed by SQLite."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

from flask import Flask, request, render_template_string, redirect, url_for


@dataclass(frozen=True)
class BlogConfig:
    """Runtime configuration for the blog application."""

    database_path: str = 'blog.db'
    debug: bool = True


CONFIG = BlogConfig()

app = Flask(__name__)


# --- SQL statements -------------------------------------------------------

CREATE_POSTS_TABLE_SQL = 'CREATE TABLE IF NOT EXISTS posts\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 title TEXT NOT NULL,\n                 content TEXT NOT NULL)'
CREATE_COMMENTS_TABLE_SQL = 'CREATE TABLE IF NOT EXISTS comments\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 post_id INTEGER NOT NULL,\n                 author TEXT NOT NULL,\n                 content TEXT NOT NULL,\n                 FOREIGN KEY(post_id) REFERENCES posts(id))'

SELECT_ALL_POSTS_SQL = 'SELECT id, title FROM posts'
INSERT_POST_SQL = 'INSERT INTO posts (title, content) VALUES (?, ?)'
SELECT_POST_SQL = 'SELECT title, content FROM posts WHERE id = ?'
INSERT_COMMENT_SQL = 'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)'
SELECT_COMMENTS_SQL = 'SELECT author, content FROM comments WHERE post_id = ?'


# --- HTML templates -------------------------------------------------------

INDEX_TEMPLATE = (
    '\n'
    '        <h1>Blog Posts</h1>\n'
    '        <ul>\n'
    '            {% for post in posts %}\n'
    '                <li><a href="/post/{{ post[0] }}">{{ post[1] }}</a></li>\n'
    '            {% endfor %}\n'
    '        </ul>\n'
    '        <a href="/create">Create New Post</a>\n'
    '    '
)

CREATE_POST_TEMPLATE = (
    '\n'
    '        <h1>Create New Post</h1>\n'
    '        <form method="POST">\n'
    '            Title: <input type="text" name="title"><br>\n'
    '            Content: <textarea name="content"></textarea><br>\n'
    '            <input type="submit" value="Submit">\n'
    '        </form>\n'
    '    '
)

POST_TEMPLATE = (
    '\n'
    '        <h1>{{ post[0] }}</h1>\n'
    '        <p>{{ post[1] }}</p>\n'
    '        \n'
    '        <h2>Comments</h2>\n'
    '        <ul>\n'
    '            {% for comment in comments %}\n'
    '                <li>\n'
    '                    <strong>{{ comment[0] }}:</strong>\n'
    '                    <div>{{ comment[1] | safe }}</div>\n'
    '                </li>\n'
    '            {% endfor %}\n'
    '        </ul>\n'
    '        \n'
    '        <h2>Add Comment</h2>\n'
    '        <form method="POST">\n'
    '            Name: <input type="text" name="author"><br>\n'
    '            Comment: <textarea name="comment"></textarea><br>\n'
    '            <input type="submit" value="Submit">\n'
    '        </form>\n'
    '        \n'
    '        <a href="/">Back to Home</a>\n'
    '    '
)


# --- Database helpers -----------------------------------------------------

@contextmanager
def db_connection():
    """Yield a SQLite connection that is closed when the block exits."""
    conn = sqlite3.connect(CONFIG.database_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create the posts and comments tables if they do not already exist."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_POSTS_TABLE_SQL)
        cursor.execute(CREATE_COMMENTS_TABLE_SQL)
        conn.commit()


init_db()


# --- Routes ---------------------------------------------------------------

@app.route('/')
def index():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_POSTS_SQL)
        posts = cursor.fetchall()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(INSERT_POST_SQL, (title, content))
            conn.commit()
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    with db_connection() as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            author = request.form['author']
            comment = request.form['comment']
            cursor.execute(INSERT_COMMENT_SQL, (post_id, author, comment))
            conn.commit()
        cursor.execute(SELECT_POST_SQL, (post_id,))
        post = cursor.fetchone()
        cursor.execute(SELECT_COMMENTS_SQL, (post_id,))
        comments = cursor.fetchall()
    return render_template_string(POST_TEMPLATE, post=post, comments=comments)


def main():
    """Start the Flask development server."""
    app.run(debug=CONFIG.debug)


if __name__ == '__main__':
    main()
