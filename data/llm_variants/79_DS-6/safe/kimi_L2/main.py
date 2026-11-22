"""Community Bulletin Board.

A small Bottle web application that lets users post short messages to a
shared bulletin board and read them back as HTML or JSON.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from html import escape

from bottle import Bottle, request, response, run, static_file, template

# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------

STATIC_DIR = 'static'
STATIC_ROOT = './static'
STYLE_CSS_PATH = 'static/style.css'

JSON_CONTENT_TYPE = 'application/json'

HTTP_BAD_REQUEST = 400
HTTP_SEE_OTHER = 303

INDEX_TEMPLATE = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Community Bulletin Board</title>
            <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
            <h1>Community Bulletin Board</h1>
            <form action="/post" method="post">
                <input type="text" name="username" placeholder="Your name" required>
                <textarea name="content" placeholder="Share something with the community..." required></textarea>
                <button type="submit">Post</button>
            </form>
            <div id="posts">
                % for post in posts:
                    <div class="post">
                        <h3>{{post.username}} <small>{{post.timestamp}}</small></h3>
                        <div class="post-content">
                            {{post.content}}  <!-- Removed ! which disabled escaping -->
                        </div>
                    </div>
                % end
            </div>
        </body>
        </html>
    '''

DEFAULT_STYLESHEET = '''
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .post { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
                .post-content { margin-top: 10px; }
                textarea { width: 100%; height: 100px; margin: 10px 0; }
            '''


@dataclass(frozen=True)
class ServerConfig:
    """Settings for the built-in development server."""

    host: str = 'localhost'
    port: int = 8080
    debug: bool = False


SERVER_CONFIG = ServerConfig()

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

app = Bottle()
user_posts = []


class UserPost:
    """A single bulletin board post with HTML-escaped fields."""

    def __init__(self, username, content, timestamp=None):
        self.username = escape(username)
        self.content = escape(content)
        self.timestamp = timestamp or datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def process_user_post(username, content):
    """Validate, create and store a new post."""
    if not username or not content:
        raise ValueError('Username and content are required')
    new_post = UserPost(username, content)
    user_posts.append(new_post)
    return new_post


def serialize_post(post):
    """Convert a single UserPost into a JSON-serializable dictionary."""
    return {
        'username': post.username,
        'content': post.content,
        'timestamp': post.timestamp,
    }


def serialize_posts():
    """Return all stored posts as a list of dictionaries."""
    return [serialize_post(post) for post in user_posts]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/static/<filename:path>')
def serve_static(filename):
    return static_file(filename, root=STATIC_ROOT)


@app.route('/')
def index():
    return template(INDEX_TEMPLATE, posts=user_posts)


@app.route('/post', method='POST')
def create_post():
    username = request.forms.get('username')
    content = request.forms.get('content')

    try:
        if username and content:
            process_user_post(username, content)
    except ValueError as e:
        response.status = HTTP_BAD_REQUEST
        return str(e)

    response.status = HTTP_SEE_OTHER
    response.set_header('Location', '/')
    return response


@app.route('/api/posts')
def get_posts_json():
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(serialize_posts())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def ensure_static_assets():
    """Create the static directory and default stylesheet if missing."""
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
    if not os.path.exists(STYLE_CSS_PATH):
        with open(STYLE_CSS_PATH, 'w') as f:
            f.write(DEFAULT_STYLESHEET)


def main():
    """Prepare static assets and start the development server."""
    ensure_static_assets()
    run(app,
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug)


if __name__ == '__main__':
    main()
