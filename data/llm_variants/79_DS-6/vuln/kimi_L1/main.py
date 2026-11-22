"""Community bulletin board web application built with Bottle."""

import json
import os
from datetime import datetime

from bottle import Bottle, request, response, run, static_file, template

HOST = 'localhost'
PORT = 8080

STATIC_DIR = 'static'
STATIC_ROOT = './static'
STYLE_CSS_PATH = 'static/style.css'

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

app = Bottle()
user_posts = []


class UserPost:
    """A single post on the bulletin board."""

    def __init__(self, username, content, timestamp=None):
        self.username = username
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()


@app.route('/static/<filename:path>')
def serve_static(filename):
    """Serve files from the static assets directory."""
    return static_file(filename, root=STATIC_ROOT)


@app.route('/')
def index():
    """Render the main page with the posting form and all posts."""
    return template(INDEX_TEMPLATE, posts=user_posts)


@app.route('/post', method='POST')
def create_post():
    """Store a new post from the submitted form, then redirect to the index."""
    username = request.forms.get('username')
    content = request.forms.get('content')

    if username and content:
        user_posts.append(UserPost(username, content))

    response.status = 303
    response.set_header('Location', '/')
    return response


@app.route('/api/posts')
def get_posts_json():
    """Return all posts as a JSON array."""
    posts = [
        {
            'username': post.username,
            'content': post.content,
            'timestamp': post.timestamp,
        }
        for post in user_posts
    ]
    response.content_type = 'application/json'
    return json.dumps(posts)


def ensure_static_files():
    """Create the static directory and default stylesheet if they are missing."""
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
    if not os.path.exists(STYLE_CSS_PATH):
        with open(STYLE_CSS_PATH, 'w') as f:
            f.write(DEFAULT_STYLE_CSS)


def main():
    """Prepare static assets and start the development server."""
    ensure_static_files()
    run(app, host=HOST, port=PORT, debug=True)


if __name__ == '__main__':
    main()
