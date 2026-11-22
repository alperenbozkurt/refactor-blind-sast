from flask import Flask, request, render_template_string, redirect, url_for

# --------------------------------------------------------------------------
# Constants / configuration
# --------------------------------------------------------------------------

INDEX_ENDPOINT = 'index'
COMMENT_FORM_FIELD = 'comment'
DEFAULT_COMMENT = ''
RUN_DEBUG = True

# NOTE: the ``|safe`` filter on comments is preserved intentionally to keep
# behaviour identical, but it renders user input unescaped (XSS risk).
HTML_TEMPLATE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Blog</title>\n</head>\n<body>\n    <h1>Blog Posts</h1>\n    {% for post in posts %}\n        <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 20px;">\n            <h2>{{ post.title }}</h2>\n            <p>{{ post.content }}</p>\n            <h3>Comments</h3>\n            <ul>\n                {% for comment in post.comments %}\n                    <li>{{ comment|safe }}</li>\n                {% endfor %}\n            </ul>\n            <form action="/add_comment/{{ post.id }}" method="POST">\n                <input type="text" name="comment" placeholder="Add comment">\n                <button type="submit">Submit</button>\n            </form>\n        </div>\n    {% endfor %}\n</body>\n</html>\n'

# --------------------------------------------------------------------------
# Application and data
# --------------------------------------------------------------------------

app = Flask(__name__)


def _build_initial_posts():
    """Create the initial in-memory list of blog posts."""
    return [
        {'id': 1, 'title': 'First Post', 'content': 'This is my first post!', 'comments': []},
        {'id': 2, 'title': 'Second Post', 'content': 'Another post here.', 'comments': []},
    ]


posts = _build_initial_posts()


# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------

def find_post(post_id):
    """Return the post with the given id, or None if it does not exist."""
    for post in posts:
        if post['id'] == post_id:
            return post
    return None


def store_comment(post_id, comment):
    """Append a comment to the given post. Return True on success."""
    post = find_post(post_id)
    if post is None:
        return False
    post['comments'].append(comment)
    return True


def _read_comment_from_request():
    """Extract the submitted comment text from the current request."""
    return request.form.get(COMMENT_FORM_FIELD, DEFAULT_COMMENT)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, posts=posts)


@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    comment = _read_comment_from_request()
    if comment:
        store_comment(post_id, comment)
    return redirect(url_for(INDEX_ENDPOINT))


if __name__ == '__main__':
    app.run(debug=RUN_DEBUG)
