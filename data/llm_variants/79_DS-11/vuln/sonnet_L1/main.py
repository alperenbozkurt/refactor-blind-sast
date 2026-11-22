from flask import Flask, request, render_template_string, redirect, url_for
import sqlite3

app = Flask(__name__)

DATABASE = 'blog.db'

CREATE_POSTS_TABLE_SQL = """CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 title TEXT NOT NULL,
                 content TEXT NOT NULL)"""

CREATE_COMMENTS_TABLE_SQL = """CREATE TABLE IF NOT EXISTS comments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 post_id INTEGER NOT NULL,
                 author TEXT NOT NULL,
                 content TEXT NOT NULL,
                 FOREIGN KEY(post_id) REFERENCES posts(id))"""

SELECT_POST_LIST_SQL = 'SELECT id, title FROM posts'
INSERT_POST_SQL = 'INSERT INTO posts (title, content) VALUES (?, ?)'
SELECT_POST_SQL = 'SELECT title, content FROM posts WHERE id = ?'
INSERT_COMMENT_SQL = 'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)'
SELECT_COMMENTS_SQL = 'SELECT author, content FROM comments WHERE post_id = ?'

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

# Note: comment content is intentionally rendered with the ``safe`` filter,
# exactly as in the original implementation.
VIEW_POST_TEMPLATE = """
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
    """


def get_connection():
    """Open a new connection to the blog database."""
    return sqlite3.connect(DATABASE)


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute(CREATE_POSTS_TABLE_SQL)
    c.execute(CREATE_COMMENTS_TABLE_SQL)
    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    conn = get_connection()
    c = conn.cursor()
    c.execute(SELECT_POST_LIST_SQL)
    posts = c.fetchall()
    conn.close()
    return render_template_string(INDEX_TEMPLATE, posts=posts)


@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn = get_connection()
        c = conn.cursor()
        c.execute(INSERT_POST_SQL, (title, content))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template_string(CREATE_POST_TEMPLATE)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    conn = get_connection()
    c = conn.cursor()
    if request.method == 'POST':
        author = request.form['author']
        comment = request.form['comment']
        c.execute(INSERT_COMMENT_SQL, (post_id, author, comment))
        conn.commit()
    c.execute(SELECT_POST_SQL, (post_id,))
    post = c.fetchone()
    c.execute(SELECT_COMMENTS_SQL, (post_id,))
    comments = c.fetchall()
    conn.close()
    return render_template_string(VIEW_POST_TEMPLATE, post=post, comments=comments)


if __name__ == '__main__':
    app.run(debug=True)
