from flask import Flask, request, render_template_string, redirect, url_for
from markupsafe import escape

app = Flask(__name__)

posts = [
    {
        'id': 1,
        'title': 'First Post',
        'content': 'This is my first post!',
        'comments': [],
    },
    {
        'id': 2,
        'title': 'Second Post',
        'content': 'Another post here.',
        'comments': [],
    },
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Blog</title>
</head>
<body>
    <h1>Blog Posts</h1>
    {% for post in posts %}
        <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 20px;">
            <h2>{{ post.title }}</h2>
            <p>{{ post.content }}</p>
            <h3>Comments</h3>
            <ul>
                {% for comment in post.comments %}
                    <li>{{ comment }}</li>
                {% endfor %}
            </ul>
            <form action="/add_comment/{{ post.id }}" method="POST">
                <input type="text" name="comment" placeholder="Add comment">
                <button type="submit">Submit</button>
            </form>
        </div>
    {% endfor %}
</body>
</html>
"""


def _store_comment(post_id, comment):
    """Escape the comment and append it to the matching post.

    Returns True if the post was found, otherwise False.
    """
    sanitized_comment = escape(comment)
    for post in posts:
        if post['id'] == post_id:
            post['comments'].append(sanitized_comment)
            return True
    return False


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, posts=posts)


@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    comment = request.form.get('comment', '')
    if comment:
        _store_comment(post_id, comment)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=False)
