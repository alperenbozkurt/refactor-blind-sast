import html
import sqlite3
from contextlib import closing

from flask import Flask, request, render_template_string, redirect, url_for

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

VIEW_POST_TEMPLATE = '''
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


def get_connection():
    """Open a new connection to the blog database."""
    return sqlite3.connect(DATABASE)


def init_db():
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_POSTS_TABLE)
        cursor.execute(CREATE_COMMENTS_TABLE)
        conn.commit()


init_db()


def fetch_all_posts():
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, title FROM posts')
        return cursor.fetchall()


def insert_post(title, content):
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO posts (title, content) VALUES (?, ?)',
            (title, content),
        )
        conn.commit()


@app.route('/')
def index():
    posts = fetch_all_posts()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        insert_post(title, content)
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            author = html.escape(request.form['author'])
            comment = html.escape(request.form['comment'])
            cursor.execute(
                'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)',
                (post_id, author, comment),
            )
            conn.commit()
        cursor.execute('SELECT title, content FROM posts WHERE id = ?', (post_id,))
        post = cursor.fetchone()
        cursor.execute(
            'SELECT author, content FROM comments WHERE post_id = ?',
            (post_id,),
        )
        comments = cursor.fetchall()
    return render_template_string(VIEW_POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=False)
