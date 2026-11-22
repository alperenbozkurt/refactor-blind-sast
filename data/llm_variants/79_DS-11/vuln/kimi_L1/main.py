"""A minimal blog application built with Flask and SQLite."""

import sqlite3

from flask import Flask, request, render_template_string, redirect, url_for

DATABASE_PATH = 'blog.db'

# SQL statements -----------------------------------------------------------

CREATE_POSTS_TABLE = 'CREATE TABLE IF NOT EXISTS posts\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 title TEXT NOT NULL,\n                 content TEXT NOT NULL)'
CREATE_COMMENTS_TABLE = 'CREATE TABLE IF NOT EXISTS comments\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 post_id INTEGER NOT NULL,\n                 author TEXT NOT NULL,\n                 content TEXT NOT NULL,\n                 FOREIGN KEY(post_id) REFERENCES posts(id))'

SELECT_ALL_POSTS = 'SELECT id, title FROM posts'
INSERT_POST = 'INSERT INTO posts (title, content) VALUES (?, ?)'
SELECT_POST_BY_ID = 'SELECT title, content FROM posts WHERE id = ?'
INSERT_COMMENT = 'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)'
SELECT_COMMENTS_BY_POST = 'SELECT author, content FROM comments WHERE post_id = ?'

# HTML templates -----------------------------------------------------------

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

VIEW_POST_TEMPLATE = (
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

app = Flask(__name__)


def get_connection():
    """Open a new connection to the blog database."""
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    """Create the posts and comments tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(CREATE_POSTS_TABLE)
    cursor.execute(CREATE_COMMENTS_TABLE)
    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    """List all blog posts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SELECT_ALL_POSTS)
    posts = cursor.fetchall()
    conn.close()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    """Display the new-post form and handle its submission."""
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(INSERT_POST, (title, content))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    """Display a single post with its comments and handle new comments."""
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        author = request.form['author']
        comment = request.form['comment']
        cursor.execute(INSERT_COMMENT, (post_id, author, comment))
        conn.commit()
    cursor.execute(SELECT_POST_BY_ID, (post_id,))
    post = cursor.fetchone()
    cursor.execute(SELECT_COMMENTS_BY_POST, (post_id,))
    comments = cursor.fetchall()
    conn.close()
    return render_template_string(VIEW_POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=True)
