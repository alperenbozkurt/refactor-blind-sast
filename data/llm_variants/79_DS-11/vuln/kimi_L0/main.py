import sqlite3

from flask import Flask, redirect, render_template_string, request, url_for

app = Flask(__name__)

DATABASE = 'blog.db'

POSTS_SCHEMA = '''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 title TEXT NOT NULL,
                 content TEXT NOT NULL)'''

COMMENTS_SCHEMA = '''CREATE TABLE IF NOT EXISTS comments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 post_id INTEGER NOT NULL,
                 author TEXT NOT NULL,
                 content TEXT NOT NULL,
                 FOREIGN KEY(post_id) REFERENCES posts(id))'''

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
                    <div>{{ comment[1] | safe }}</div>
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
    return sqlite3.connect(DATABASE)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(POSTS_SCHEMA)
    cursor.execute(COMMENTS_SCHEMA)
    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, title FROM posts')
    posts = cursor.fetchall()
    conn.close()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO posts (title, content) VALUES (?, ?)',
            (title, content),
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        author = request.form['author']
        comment = request.form['comment']
        cursor.execute(
            'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)',
            (post_id, author, comment),
        )
        conn.commit()
    cursor.execute('SELECT title, content FROM posts WHERE id = ?', (post_id,))
    post = cursor.fetchone()
    cursor.execute('SELECT author, content FROM comments WHERE post_id = ?', (post_id,))
    comments = cursor.fetchall()
    conn.close()
    return render_template_string(VIEW_POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=True)
