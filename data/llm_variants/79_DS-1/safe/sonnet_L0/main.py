from flask import Flask, request, render_template_string, redirect, url_for
from markupsafe import escape

app = Flask(__name__)

posts = [
    {'id': 1, 'title': 'First Post', 'content': 'This is my first post!', 'comments': []},
    {'id': 2, 'title': 'Second Post', 'content': 'Another post here.', 'comments': []},
]

HTML_TEMPLATE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Blog</title>\n</head>\n<body>\n    <h1>Blog Posts</h1>\n    {% for post in posts %}\n        <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 20px;">\n            <h2>{{ post.title }}</h2>\n            <p>{{ post.content }}</p>\n            <h3>Comments</h3>\n            <ul>\n                {% for comment in post.comments %}\n                    <li>{{ comment }}</li>\n                {% endfor %}\n            </ul>\n            <form action="/add_comment/{{ post.id }}" method="POST">\n                <input type="text" name="comment" placeholder="Add comment">\n                <button type="submit">Submit</button>\n            </form>\n        </div>\n    {% endfor %}\n</body>\n</html>\n'


def _store_comment(post_id, comment):
    """Append an escaped comment to the post with the given id.

    Returns True if the post was found, otherwise False.
    """
    post = next((p for p in posts if p['id'] == post_id), None)
    if post is None:
        return False
    post['comments'].append(escape(comment))
    return True


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
