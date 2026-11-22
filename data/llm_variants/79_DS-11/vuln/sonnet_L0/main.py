from contextlib import closing

from flask import Flask, request, render_template_string, redirect, url_for
import sqlite3

app = Flask(__name__)

DATABASE = 'blog.db'

CREATE_POSTS_TABLE = (
    'CREATE TABLE IF NOT EXISTS posts\n'
    '                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                 title TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL)'
)

CREATE_COMMENTS_TABLE = (
    'CREATE TABLE IF NOT EXISTS comments\n'
    '                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '                 post_id INTEGER NOT NULL,\n'
    '                 author TEXT NOT NULL,\n'
    '                 content TEXT NOT NULL,\n'
    '                 FOREIGN KEY(post_id) REFERENCES posts(id))'
)

INDEX_TEMPLATE = (
    '\n        <h1>Blog Posts</h1>\n        <ul>\n'
    '            {% for post in posts %}\n'
    '                <li><a href="/post/{{ post[0] }}">{{ post[1] }}</a></li>\n'
    '            {% endfor %}\n'
    '        </ul>\n'
    '        <a href="/create">Create New Post</a>\n    '
)

CREATE_TEMPLATE = (
    '\n        <h1>Create New Post</h1>\n'
    '        <form method="POST">\n'
    '            Title: <input type="text" name="title"><br>\n'
    '            Content: <textarea name="content"></textarea><br>\n'
    '            <input type="submit" value="Submit">\n'
    '        </form>\n    '
)

# NOTE: the "| safe" filter on comment content is preserved to keep behaviour
# identical, but it renders user-supplied HTML unescaped.
POST_TEMPLATE = (
    '\n        <h1>{{ post[0] }}</h1>\n'
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
    '        <a href="/">Back to Home</a>\n    '
)


def get_connection():
    return closing(sqlite3.connect(DATABASE))


def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(CREATE_POSTS_TABLE)
        c.execute(CREATE_COMMENTS_TABLE)
        conn.commit()


init_db()


@app.route('/')
def index():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, title FROM posts')
        posts = c.fetchall()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        with get_connection() as conn:
            c = conn.cursor()
            c.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                      (title, content))
            conn.commit()
        return redirect(url_for('index'))
    return render_template_string(CREATE_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    with get_connection() as conn:
        c = conn.cursor()
        if request.method == 'POST':
            author = request.form['author']
            comment = request.form['comment']
            c.execute(
                'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)',
                (post_id, author, comment))
            conn.commit()
        c.execute('SELECT title, content FROM posts WHERE id = ?', (post_id,))
        post = c.fetchone()
        c.execute('SELECT author, content FROM comments WHERE post_id = ?',
                  (post_id,))
        comments = c.fetchall()
    return render_template_string(POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=True)
