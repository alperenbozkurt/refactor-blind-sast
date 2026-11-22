from bottle import Bottle, run, request, response, template, static_file
import os
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

STATIC_ROOT = './static'
STATIC_DIR = 'static'
STYLE_CSS_PATH = 'static/style.css'

SERVER_HOST = 'localhost'
SERVER_PORT = 8080
SERVER_DEBUG = True

REDIRECT_STATUS = 303
REDIRECT_LOCATION = '/'
JSON_CONTENT_TYPE = 'application/json'

# NOTE: the template intentionally renders post content unescaped
# ({{!post.content}}) to preserve the original behaviour.
INDEX_TEMPLATE = (
    '\n'
    '        <!DOCTYPE html>\n'
    '        <html>\n'
    '        <head>\n'
    '            <title>Community Bulletin Board</title>\n'
    '            <link rel="stylesheet" href="/static/style.css">\n'
    '        </head>\n'
    '        <body>\n'
    '            <h1>Community Bulletin Board</h1>\n'
    '            <form action="/post" method="post">\n'
    '                <input type="text" name="username" placeholder="Your name" required>\n'
    '                <textarea name="content" placeholder="Share something with the community..." required></textarea>\n'
    '                <button type="submit">Post</button>\n'
    '            </form>\n'
    '            <div id="posts">\n'
    '                % for post in posts:\n'
    '                    <div class="post">\n'
    '                        <h3>{{post.username}} <small>{{post.timestamp}}</small></h3>\n'
    '                        <div class="post-content">\n'
    '                            {{!post.content}}\n'
    '                        </div>\n'
    '                    </div>\n'
    '                % end\n'
    '            </div>\n'
    '        </body>\n'
    '        </html>\n'
    '    '
)

DEFAULT_STYLE_CSS = (
    '\n'
    '                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n'
    '                .post { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }\n'
    '                .post-content { margin-top: 10px; }\n'
    '                textarea { width: 100%; height: 100px; margin: 10px 0; }\n'
    '            '
)

# ---------------------------------------------------------------------------
# Application state and models
# ---------------------------------------------------------------------------

app = Bottle()
user_posts = []


class UserPost:

    def __init__(self, username, content, timestamp=None):
        self.username = username
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def process_user_post(username, content):
    new_post = UserPost(username, content)
    user_posts.append(new_post)
    return new_post


def serialize_post(post):
    return {
        'username': post.username,
        'content': post.content,
        'timestamp': post.timestamp,
    }


def serialize_posts():
    return [serialize_post(post) for post in user_posts]


def redirect_to_index():
    response.status = REDIRECT_STATUS
    response.set_header('Location', REDIRECT_LOCATION)
    return response


def ensure_static_assets():
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
    if not os.path.exists(STYLE_CSS_PATH):
        with open(STYLE_CSS_PATH, 'w') as f:
            f.write(DEFAULT_STYLE_CSS)


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
    if username and content:
        process_user_post(username, content)
    return redirect_to_index()


@app.route('/api/posts')
def get_posts_json():
    response.content_type = JSON_CONTENT_TYPE
    return json.dumps(serialize_posts())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ensure_static_assets()
    run(app, host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
