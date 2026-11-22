import json
import os
from datetime import datetime
from html import escape

from bottle import Bottle, run, request, response, template, static_file

STATIC_DIR = 'static'
STYLESHEET_PATH = 'static/style.css'

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

DEFAULT_CSS = '''
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .post { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
                .post-content { margin-top: 10px; }
                textarea { width: 100%; height: 100px; margin: 10px 0; }
            '''

app = Bottle()
user_posts = []


class UserPost:
    """A single bulletin board post with HTML-escaped user-supplied fields."""

    def __init__(self, username, content, timestamp=None):
        self.username = escape(username)
        self.content = escape(content)
        self.timestamp = timestamp or datetime.now().isoformat()


def _serialize_posts():
    return [
        {
            'username': post.username,
            'content': post.content,
            'timestamp': post.timestamp,
        }
        for post in user_posts
    ]


def _ensure_static_assets():
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
    if not os.path.exists(STYLESHEET_PATH):
        with open(STYLESHEET_PATH, 'w') as f:
            f.write(DEFAULT_CSS)


@app.route('/static/<filename:path>')
def serve_static(filename):
    return static_file(filename, root='./static')


@app.route('/')
def index():
    return template(INDEX_TEMPLATE, posts=user_posts)


@app.route('/post', method='POST')
def create_post():
    username = request.forms.get('username')
    content = request.forms.get('content')

    # Posts with a missing username or content are silently ignored.
    if username and content:
        user_posts.append(UserPost(username, content))

    response.status = 303
    response.set_header('Location', '/')
    return response


@app.route('/api/posts')
def get_posts_json():
    response.content_type = 'application/json'
    return json.dumps(_serialize_posts())


if __name__ == '__main__':
    _ensure_static_assets()
    run(app, host='localhost', port=8080, debug=False)
