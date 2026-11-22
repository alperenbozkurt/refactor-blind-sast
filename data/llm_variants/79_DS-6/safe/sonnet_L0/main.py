from bottle import Bottle, run, request, response, template, static_file
import os
import json
from datetime import datetime
from html import escape

app = Bottle()
user_posts = []

STATIC_ROOT = './static'
STATIC_DIR = 'static'
STYLE_PATH = 'static/style.css'

INDEX_TEMPLATE = '\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Community Bulletin Board</title>\n            <link rel="stylesheet" href="/static/style.css">\n        </head>\n        <body>\n            <h1>Community Bulletin Board</h1>\n            <form action="/post" method="post">\n                <input type="text" name="username" placeholder="Your name" required>\n                <textarea name="content" placeholder="Share something with the community..." required></textarea>\n                <button type="submit">Post</button>\n            </form>\n            <div id="posts">\n                % for post in posts:\n                    <div class="post">\n                        <h3>{{post.username}} <small>{{post.timestamp}}</small></h3>\n                        <div class="post-content">\n                            {{post.content}}  <!-- Removed ! which disabled escaping -->\n                        </div>\n                    </div>\n                % end\n            </div>\n        </body>\n        </html>\n    '

DEFAULT_CSS = '\n                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n                .post { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }\n                .post-content { margin-top: 10px; }\n                textarea { width: 100%; height: 100px; margin: 10px 0; }\n            '


class UserPost:

    def __init__(self, username, content, timestamp=None):
        self.username = escape(username)
        self.content = escape(content)
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self):
        return {
            'username': self.username,
            'content': self.content,
            'timestamp': self.timestamp,
        }


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
        user_posts.append(UserPost(username, content))
    response.status = 303
    response.set_header('Location', '/')
    return response


@app.route('/api/posts')
def get_posts_json():
    response.content_type = 'application/json'
    return json.dumps([post.to_dict() for post in user_posts])


def ensure_static_assets():
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
    if not os.path.exists(STYLE_PATH):
        with open(STYLE_PATH, 'w') as f:
            f.write(DEFAULT_CSS)


if __name__ == '__main__':
    ensure_static_assets()
    run(app, host='localhost', port=8080, debug=False)
