"""Community Bulletin Board web application.

A small Bottle-based app that lets users post short messages to a shared,
in-memory bulletin board and exposes the posts as JSON.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime

from bottle import Bottle, run, request, response, template, static_file

STATIC_FILE_ROOT = './static'
STATIC_DIR = 'static'
STYLE_CSS_PATH = os.path.join(STATIC_DIR, 'style.css')

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
                            {{!post.content}}
                        </div>
                    </div>
                % end
            </div>
        </body>
        </html>
    '''

DEFAULT_STYLE_CSS = '''
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .post { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
                .post-content { margin-top: 10px; }
                textarea { width: 100%; height: 100px; margin: 10px 0; }
            '''


@dataclass(frozen=True)
class ServerConfig:
    """Settings used when starting the development server."""
    host: str = 'localhost'
    port: int = 8080
    debug: bool = True


@dataclass(frozen=True)
class StaticAssetsConfig:
    """Locations and default content for the bundled static assets."""
    directory: str = STATIC_DIR
    stylesheet_path: str = STYLE_CSS_PATH
    stylesheet_content: str = DEFAULT_STYLE_CSS


app = Bottle()
user_posts = []


class UserPost:
    """A single bulletin board entry."""

    def __init__(self, username, content, timestamp=None):
        self.username = username
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()


def process_user_post(username, content):
    """Create a ``UserPost`` and append it to the global ``user_posts`` list."""
    new_post = UserPost(username, content)
    user_posts.append(new_post)
    return new_post


def serialize_post(post):
    """Convert a ``UserPost`` into a JSON-serializable dictionary."""
    return {
        'username': post.username,
        'content': post.content,
        'timestamp': post.timestamp,
    }


def serialize_posts():
    """Serialize every post currently stored in ``user_posts``."""
    return [serialize_post(post) for post in user_posts]


@app.route('/static/<filename:path>')
def serve_static(filename):
    return static_file(filename, root=STATIC_FILE_ROOT)


@app.route('/')
def index():
    return template(INDEX_TEMPLATE, posts=user_posts)


@app.route('/post', method='POST')
def create_post():
    username = request.forms.get('username')
    content = request.forms.get('content')
    if username and content:
        process_user_post(username, content)
    response.status = 303
    response.set_header('Location', '/')
    return response


@app.route('/api/posts')
def get_posts_json():
    response.content_type = 'application/json'
    return json.dumps(serialize_posts())


def ensure_static_assets(config=None):
    """Create the static asset directory and default stylesheet if missing."""
    config = config or StaticAssetsConfig()
    if not os.path.exists(config.directory):
        os.makedirs(config.directory)
    if not os.path.exists(config.stylesheet_path):
        with open(config.stylesheet_path, 'w') as f:
            f.write(config.stylesheet_content)


def main():
    """Entry point: prepare static assets and start the development server."""
    ensure_static_assets()
    config = ServerConfig()
    run(app, host=config.host, port=config.port, debug=config.debug)


if __name__ == '__main__':
    main()
