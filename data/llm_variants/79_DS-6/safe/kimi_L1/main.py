"""Community Bulletin Board web application built with Bottle."""

import json
import os
from datetime import datetime
from html import escape

from bottle import Bottle, request, response, run, static_file, template

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

STYLE_CSS = '''
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .post { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
                .post-content { margin-top: 10px; }
                textarea { width: 100%; height: 100px; margin: 10px 0; }
            '''

app = Bottle()
user_posts = []


class UserPost:
    """A single bulletin-board post with HTML-escaped username and content."""

    def __init__(self, username, content, timestamp=None):
        self.username = escape(username)
        self.content = escape(content)
        self.timestamp = timestamp or datetime.now().isoformat()


@app.route('/static/<filename:path>')
def serve_static(filename):
    """Serve a static file from the ./static directory."""
    return static_file(filename, root='./static')


@app.route('/')
def index():
    """Render the bulletin board page with all current posts."""
    return template(INDEX_TEMPLATE, posts=user_posts)


@app.route('/post', method='POST')
def create_post():
    """Create a new post from the submitted form and redirect to the board."""
    username = request.forms.get('username')
    content = request.forms.get('content')

    def process_user_post(username, content):
        if not username or not content:
            raise ValueError('Username and content are required')
        new_post = UserPost(username, content)
        user_posts.append(new_post)
        return new_post

    try:
        if username and content:
            process_user_post(username, content)
    except ValueError as e:
        response.status = 400
        return str(e)
    response.status = 303
    response.set_header('Location', '/')
    return response


@app.route('/api/posts')
def get_posts_json():
    """Return all current posts as a JSON array."""

    def serialize_posts():
        return [
            {
                'username': post.username,
                'content': post.content,
                'timestamp': post.timestamp,
            }
            for post in user_posts
        ]

    response.content_type = 'application/json'
    return json.dumps(serialize_posts())


if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists('static/style.css'):
        with open('static/style.css', 'w') as f:
            f.write(STYLE_CSS)
    run(app, host='localhost', port=8080, debug=False)
