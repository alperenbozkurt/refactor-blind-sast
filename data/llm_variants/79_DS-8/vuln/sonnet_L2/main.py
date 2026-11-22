from quart import Quart, request, render_template_string, redirect, url_for
from datetime import datetime
import bleach
import hashlib

app = Quart(__name__)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class ServerConfig:
    """Network settings used when running the development server."""

    HOST = '0.0.0.0'
    PORT = 5000


PAGE_NOT_FOUND_MESSAGE = 'Page not found'
PAGE_NOT_FOUND_STATUS = 404

DEFAULT_HOME_PAGE_ID = 'home'
DEFAULT_HOME_PAGE_TITLE = 'Welcome'
DEFAULT_HOME_PAGE_CONTENT = '<p>Welcome to our documentation system</p>'
DEFAULT_HOME_PAGE_AUTHOR = 'admin'


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
INDEX_TEMPLATE = '\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Documentation System</title>\n            <style>\n                .page { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }\n                .actions { margin: 20px 0; }\n            </style>\n        </head>\n        <body>\n            <h1>Documentation Pages</h1>\n            <div class="actions">\n                <a href="/new">Create New Page</a>\n            </div>\n            {% for page_id, page in pages.items() %}\n                <div class="page">\n                    <h2><a href="/page/{{ page_id }}">{{ page.title }}</a></h2>\n                    <p>Last modified: {{ page.last_modified }} by {{ page.author }}</p>\n                </div>\n            {% endfor %}\n        </body>\n        </html>\n    '

NEW_PAGE_TEMPLATE = '\n            <!DOCTYPE html>\n            <html>\n            <head>\n                <title>Create New Page</title>\n            </head>\n            <body>\n                <h1>Create New Documentation Page</h1>\n                <form method="POST">\n                    <input type="text" name="page_id" placeholder="Page ID" required><br>\n                    <input type="text" name="title" placeholder="Title" required><br>\n                    <textarea name="content" placeholder="Content (HTML)" required></textarea><br>\n                    <input type="text" name="author" placeholder="Your name" required><br>\n                    <button type="submit">Create Page</button>\n                </form>\n            </body>\n            </html>\n        '

EDIT_PAGE_TEMPLATE = '\n            <!DOCTYPE html>\n            <html>\n            <head>\n                <title>Edit {{ page.title }}</title>\n            </head>\n            <body>\n                <h1>Edit {{ page.title }}</h1>\n                <form method="POST">\n                    <input type="text" name="title" value="{{ page.title }}" required><br>\n                    <textarea name="content" required>{{ page.content }}</textarea><br>\n                    <input type="text" name="author" value="{{ page.author }}" required><br>\n                    <button type="submit">Save Changes</button>\n                </form>\n            </body>\n            </html>\n        '


def render_documentation_page(page, page_id):
    """Build the HTML for a single documentation page."""
    return f"""\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>{page['title']}</title>\n        </head>\n        <body>\n            <h1>{page['title']}</h1>\n            <div class="content">\n                {page['content']}\n            </div>\n            <p><small>Last modified: {page['last_modified']} by {page['author']}</small></p>\n            <a href="/edit/{page_id}">Edit this page</a> | \n            <a href="/">Back to index</a>\n        </body>\n        </html>\n        """


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
def _timestamp():
    return datetime.now().isoformat()


def _make_page(title, content, author):
    return {
        'title': title,
        'content': content,
        'last_modified': _timestamp(),
        'author': author,
    }


def _make_page_from_form(form):
    return _make_page(form['title'], form['content'], form['author'])


def _page_not_found():
    return (PAGE_NOT_FOUND_MESSAGE, PAGE_NOT_FOUND_STATUS)


def _redirect_to_page(page_id):
    return redirect(url_for('view_page', page_id=page_id))


documentation_pages = {
    DEFAULT_HOME_PAGE_ID: _make_page(
        DEFAULT_HOME_PAGE_TITLE,
        DEFAULT_HOME_PAGE_CONTENT,
        DEFAULT_HOME_PAGE_AUTHOR,
    )
}


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
async def index():
    return await render_template_string(INDEX_TEMPLATE, pages=documentation_pages)


@app.route('/page/<page_id>')
async def view_page(page_id):
    if page_id not in documentation_pages:
        return _page_not_found()
    return render_documentation_page(documentation_pages[page_id], page_id)


@app.route('/new', methods=['GET', 'POST'])
async def new_page():
    if request.method == 'GET':
        return await render_template_string(NEW_PAGE_TEMPLATE)
    form = await request.form
    page_id = form['page_id']
    documentation_pages[page_id] = _make_page_from_form(form)
    return _redirect_to_page(page_id)


@app.route('/edit/<page_id>', methods=['GET', 'POST'])
async def edit_page(page_id):
    if page_id not in documentation_pages:
        return _page_not_found()
    if request.method == 'GET':
        return await render_template_string(
            EDIT_PAGE_TEMPLATE, page=documentation_pages[page_id]
        )
    form = await request.form
    documentation_pages[page_id] = _make_page_from_form(form)
    return _redirect_to_page(page_id)


if __name__ == '__main__':
    app.run(host=ServerConfig.HOST, port=ServerConfig.PORT)
