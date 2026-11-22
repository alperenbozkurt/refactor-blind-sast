"""Simple in-memory Flask blog application."""

from dataclasses import dataclass

from flask import Flask, redirect, render_template_string, request, url_for


@dataclass(frozen=True)
class BlogConfig:
    """Runtime configuration for the blog application."""

    debug: bool = True
    comment_form_field: str = 'comment'
    default_comment: str = ''


CONFIG = BlogConfig()

app = Flask(__name__)

HTML_TEMPLATE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Blog</title>\n</head>\n<body>\n    <h1>Blog Posts</h1>\n    {% for post in posts %}\n        <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 20px;">\n            <h2>{{ post.title }}</h2>\n            <p>{{ post.content }}</p>\n            <h3>Comments</h3>\n            <ul>\n                {% for comment in post.comments %}\n                    <li>{{ comment|safe }}</li>\n                {% endfor %}\n            </ul>\n            <form action="/add_comment/{{ post.id }}" method="POST">\n                <input type="text" name="comment" placeholder="Add comment">\n                <button type="submit">Submit</button>\n            </form>\n        </div>\n    {% endfor %}\n</body>\n</html>\n'


def _seed_posts():
    """Return the initial in-memory collection of blog posts."""
    return [
        {'id': 1, 'title': 'First Post', 'content': 'This is my first post!', 'comments': []},
        {'id': 2, 'title': 'Second Post', 'content': 'Another post here.', 'comments': []},
    ]


posts = _seed_posts()


def _find_post(post_id):
    """Return the post matching ``post_id``, or ``None`` if not found."""
    for post in posts:
        if post['id'] == post_id:
            return post
    return None


def store_comment(post_id, comment):
    """Append ``comment`` to the matching post.

    Returns ``True`` if the post exists, otherwise ``False``.
    """
    post = _find_post(post_id)
    if post is None:
        return False
    post['comments'].append(comment)
    return True


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, posts=posts)


@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    comment = request.form.get(CONFIG.comment_form_field, CONFIG.default_comment)
    if comment:
        store_comment(post_id, comment)
    return redirect(url_for('index'))


def main():
    """Run the development server."""
    app.run(debug=CONFIG.debug)


if __name__ == '__main__':
    main()
