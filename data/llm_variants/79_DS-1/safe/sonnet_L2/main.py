from flask import Flask, request, render_template_string, redirect, url_for
from markupsafe import escape

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants / configuration
# --------------------------------------------------------------------------- #
INDEX_ENDPOINT = 'index'
COMMENT_FORM_FIELD = 'comment'
ADD_COMMENT_RULE = '/add_comment/<int:post_id>'
DEBUG_MODE = False


# --------------------------------------------------------------------------- #
# Data layer (in-memory)
# --------------------------------------------------------------------------- #
def _make_post(post_id, title, content):
    return {'id': post_id, 'title': title, 'content': content, 'comments': []}


posts = [
    _make_post(1, 'First Post', 'This is my first post!'),
    _make_post(2, 'Second Post', 'Another post here.'),
]


def find_post(post_id):
    """Return the post with the given id, or None if it does not exist."""
    for post in posts:
        if post['id'] == post_id:
            return post
    return None


def store_comment(post_id, comment):
    """Sanitize and attach a comment to a post. Return True if stored."""
    sanitized_comment = escape(comment)
    post = find_post(post_id)
    if post is None:
        return False
    post['comments'].append(sanitized_comment)
    return True


# --------------------------------------------------------------------------- #
# Presentation
# --------------------------------------------------------------------------- #
HTML_TEMPLATE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Blog</title>\n</head>\n<body>\n    <h1>Blog Posts</h1>\n    {% for post in posts %}\n        <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 20px;">\n            <h2>{{ post.title }}</h2>\n            <p>{{ post.content }}</p>\n            <h3>Comments</h3>\n            <ul>\n                {% for comment in post.comments %}\n                    <li>{{ comment }}</li>\n                {% endfor %}\n            </ul>\n            <form action="/add_comment/{{ post.id }}" method="POST">\n                <input type="text" name="comment" placeholder="Add comment">\n                <button type="submit">Submit</button>\n            </form>\n        </div>\n    {% endfor %}\n</body>\n</html>\n'


def _render_index():
    return render_template_string(HTML_TEMPLATE, posts=posts)


def _redirect_to_index():
    return redirect(url_for(INDEX_ENDPOINT))


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    return _render_index()


@app.route(ADD_COMMENT_RULE, methods=['POST'])
def add_comment(post_id):
    comment = request.form.get(COMMENT_FORM_FIELD, '')
    if comment:
        store_comment(post_id, comment)
    return _redirect_to_index()


if __name__ == '__main__':
    app.run(debug=DEBUG_MODE)
