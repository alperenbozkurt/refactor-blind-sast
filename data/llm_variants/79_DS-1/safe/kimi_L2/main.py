"""Minimal Flask blog application with per-post comments.

The module is organised into small, well-named pieces -- configuration,
seed data, data-access helpers, view functions and a CLI entry point --
so it can grow cleanly inside a larger production codebase.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, redirect, render_template_string, request, url_for
from markupsafe import escape


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the blog application."""

    debug: bool = False
    comment_form_field: str = 'comment'
    default_comment: str = ''
    index_endpoint: str = 'index'


CONFIG = AppConfig()

INDEX_ROUTE = '/'
ADD_COMMENT_ROUTE = '/add_comment/<int:post_id>'
POST_METHODS = ['POST']


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

Post = Dict[str, Any]


def _make_post(post_id: int, title: str, content: str) -> Post:
    """Build a post record with an empty comment list."""
    return {'id': post_id, 'title': title, 'content': content, 'comments': []}


_SEED_POSTS: Tuple[Tuple[int, str, str], ...] = (
    (1, 'First Post', 'This is my first post!'),
    (2, 'Second Post', 'Another post here.'),
)

posts: List[Post] = [
    _make_post(post_id, title, content)
    for post_id, title, content in _SEED_POSTS
]


def _find_post(post_id: int) -> Optional[Post]:
    """Return the post with ``post_id``, or ``None`` when it does not exist."""
    for post in posts:
        if post['id'] == post_id:
            return post
    return None


def store_comment(post_id: int, comment: str) -> bool:
    """Sanitise ``comment`` and attach it to the post with ``post_id``.

    Returns ``True`` when the post exists and the comment was stored,
    ``False`` otherwise.
    """
    sanitized_comment = escape(comment)
    post = _find_post(post_id)
    if post is None:
        return False
    post['comments'].append(sanitized_comment)
    return True


# ---------------------------------------------------------------------------
# Application and views
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route(INDEX_ROUTE)
def index():
    """Render every blog post together with its comments."""
    return render_template_string(HTML_TEMPLATE, posts=posts)


@app.route(ADD_COMMENT_ROUTE, methods=POST_METHODS)
def add_comment(post_id):
    """Store a submitted comment and redirect back to the index page."""
    comment = request.form.get(CONFIG.comment_form_field, CONFIG.default_comment)
    if comment:
        store_comment(post_id, comment)
    return redirect(url_for(CONFIG.index_endpoint))


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Flask development server."""
    app.run(debug=CONFIG.debug)


if __name__ == '__main__':
    main()
