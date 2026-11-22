from contextlib import closing

from flask import Flask, request, render_template_string, redirect, url_for
import sqlite3

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

DB_PATH = 'blog.db'

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

SCHEMA_STATEMENTS = (CREATE_POSTS_TABLE_SQL, CREATE_COMMENTS_TABLE_SQL)

SELECT_POST_LIST_SQL = 'SELECT id, title FROM posts'
INSERT_POST_SQL = 'INSERT INTO posts (title, content) VALUES (?, ?)'
SELECT_POST_SQL = 'SELECT title, content FROM posts WHERE id = ?'
INSERT_COMMENT_SQL = 'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)'
SELECT_COMMENTS_SQL = 'SELECT author, content FROM comments WHERE post_id = ?'

INDEX_TEMPLATE = '\n        <h1>Blog Posts</h1>\n        <ul>\n            {% for post in posts %}\n                <li><a href="/post/{{ post[0] }}">{{ post[1] }}</a></li>\n            {% endfor %}\n        </ul>\n        <a href="/create">Create New Post</a>\n    '

CREATE_POST_TEMPLATE = '\n        <h1>Create New Post</h1>\n        <form method="POST">\n            Title: <input type="text" name="title"><br>\n            Content: <textarea name="content"></textarea><br>\n            <input type="submit" value="Submit">\n        </form>\n    '

# NOTE: comment content is rendered with ``| safe`` (unescaped). This is
# preserved intentionally to keep behaviour identical, but it allows stored
# XSS and should be reviewed.
VIEW_POST_TEMPLATE = '\n        <h1>{{ post[0] }}</h1>\n        <p>{{ post[1] }}</p>\n        \n        <h2>Comments</h2>\n        <ul>\n            {% for comment in comments %}\n                <li>\n                    <strong>{{ comment[0] }}:</strong>\n                    <div>{{ comment[1] | safe }}</div>\n                </li>\n            {% endfor %}\n        </ul>\n        \n        <h2>Add Comment</h2>\n        <form method="POST">\n            Name: <input type="text" name="author"><br>\n            Comment: <textarea name="comment"></textarea><br>\n            <input type="submit" value="Submit">\n        </form>\n        \n        <a href="/">Back to Home</a>\n    '


# --------------------------------------------------------------------------- #
# Data access layer
# --------------------------------------------------------------------------- #

def _connect():
    """Open a new connection to the blog database."""
    return sqlite3.connect(DB_PATH)


def _list_posts(cursor):
    cursor.execute(SELECT_POST_LIST_SQL)
    return cursor.fetchall()


def _insert_post(conn, title, content):
    conn.cursor().execute(INSERT_POST_SQL, (title, content))
    conn.commit()


def _get_post(cursor, post_id):
    cursor.execute(SELECT_POST_SQL, (post_id,))
    return cursor.fetchone()


def _insert_comment(conn, cursor, post_id, author, comment):
    cursor.execute(INSERT_COMMENT_SQL, (post_id, author, comment))
    conn.commit()


def _get_comments(cursor, post_id):
    cursor.execute(SELECT_COMMENTS_SQL, (post_id,))
    return cursor.fetchall()


def init_db():
    with closing(_connect()) as conn:
        c = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            c.execute(statement)
        conn.commit()


init_db()


# --------------------------------------------------------------------------- #
# Request handlers
# --------------------------------------------------------------------------- #

def _handle_create_submission():
    title = request.form['title']
    content = request.form['content']
    with closing(_connect()) as conn:
        _insert_post(conn, title, content)
    return redirect(url_for('index'))


def _handle_comment_submission(conn, cursor, post_id):
    author = request.form['author']
    comment = request.form['comment']
    _insert_comment(conn, cursor, post_id, author, comment)


@app.route('/')
def index():
    with closing(_connect()) as conn:
        posts = _list_posts(conn.cursor())
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        return _handle_create_submission()
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    with closing(_connect()) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            _handle_comment_submission(conn, c, post_id)
        post = _get_post(c, post_id)
        comments = _get_comments(c, post_id)
    return render_template_string(VIEW_POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=True)
