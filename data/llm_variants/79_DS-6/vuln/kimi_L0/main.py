import json
import os
from datetime import datetime

from bottle import Bottle, request, response, run, static_file, template

app = Bottle()
user_posts = []

INDEX_TEMPLATE = """
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
    """

DEFAULT_STYLESHEET = """
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .post { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
                .post-content { margin-top: 10px; }
                textarea { width: 100%; height: 100px; margin: 10px 0; }
            """


class UserPost:

    def __init__(self, username, content, timestamp=None):
        self.username = username
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()


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
    if username and content:
        user_posts.append(UserPost(username, content))
    response.status = 303
    response.set_header('Location', '/')
    return response


@app.route('/api/posts')
def get_posts_json():
    posts = [
        {'username': post.username, 'content': post.content, 'timestamp': post.timestamp}
        for post in user_posts
    ]
    response.content_type = 'application/json'
    return json.dumps(posts)


if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists('static/style.css'):
        with open('static/style.css', 'w') as f:
            f.write(DEFAULT_STYLESHEET)
    run(app, host='localhost', port=8080, debug=True)
