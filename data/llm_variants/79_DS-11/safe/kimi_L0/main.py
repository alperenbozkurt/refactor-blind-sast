import html
import sqlite3
from contextlib import closing

from flask import Flask, redirect, render_template_string, request, url_for

DATABASE = 'blog.db'

app = Flask(__name__)

INDEX_TEMPLATE = '''
        <h1>Blog Posts</h1>
        <ul>
            {% for post in posts %}
                <li><a href="/post/{{ post[0] }}">{{ post[1] }}</a></li>
            {% endfor %}
        </ul>
        <a href="/create">Create New Post</a>
    '''

CREATE_POST_TEMPLATE = '''
        <h1>Create New Post</h1>
        <form method="POST">
            Title: <input type="text" name="title"><br>
            Content: <textarea name="content"></textarea><br>
            <input type="submit" value="Submit">
        </form>
    '''

POST_TEMPLATE = '''
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
    '''


def get_db_connection():
    """Return a new connection to the blog database."""
    return sqlite3.connect(DATABASE)


def fetch_all(query, params=()):
    """Execute a read query and return all resulting rows."""
    with closing(get_db_connection()) as conn:
        return conn.execute(query, params).fetchall()


def fetch_one(query, params=()):
    """Execute a read query and return the first resulting row."""
    with closing(get_db_connection()) as conn:
        return conn.execute(query, params).fetchone()


def run_write(query, params=()):
    """Execute a write query and commit the change."""
    with closing(get_db_connection()) as conn:
        conn.execute(query, params)
        conn.commit()


def init_db():
    with closing(get_db_connection()) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS posts\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 title TEXT NOT NULL,\n                 content TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS comments\n                 (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                 post_id INTEGER NOT NULL,\n                 author TEXT NOT NULL,\n                 content TEXT NOT NULL,\n                 FOREIGN KEY(post_id) REFERENCES posts(id))')
        conn.commit()


init_db()


@app.route('/')
def index():
    posts = fetch_all('SELECT id, title FROM posts')
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        run_write(
            'INSERT INTO posts (title, content) VALUES (?, ?)',
            (request.form['title'], request.form['content']),
        )
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    if request.method == 'POST':
        author = html.escape(request.form['author'])
        comment = html.escape(request.form['comment'])
        run_write(
            'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)',
            (post_id, author, comment),
        )
    post = fetch_one('SELECT title, content FROM posts WHERE id = ?', (post_id,))
    comments = fetch_all('SELECT author, content FROM comments WHERE post_id = ?', (post_id,))
    return render_template_string(POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=False)
