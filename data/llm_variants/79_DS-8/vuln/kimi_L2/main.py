"""Documentation system web application.

A small Quart-based wiki/documentation server backed by an in-memory
page store. The module is organised into configuration constants, HTML
template constants, and small helper functions, while the public routes,
module-level names and CLI remain unchanged.
"""

from quart import Quart, request, render_template_string, redirect, url_for
from datetime import datetime
import bleach
import hashlib

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

PAGE_NOT_FOUND_MESSAGE = 'Page not found'
PAGE_NOT_FOUND_STATUS = 404
PAGE_NOT_FOUND_RESPONSE = (PAGE_NOT_FOUND_MESSAGE, PAGE_NOT_FOUND_STATUS)

DEFAULT_PAGE_ID = 'home'
DEFAULT_PAGE_TITLE = 'Welcome'
DEFAULT_PAGE_CONTENT = '<p>Welcome to our documentation system</p>'
DEFAULT_PAGE_AUTHOR = 'admin'

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = '\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Documentation System</title>\n            <style>\n                .page { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }\n                .actions { margin: 20px 0; }\n            </style>\n        </head>\n        <body>\n            <h1>Documentation Pages</h1>\n            <div class="actions">\n                <a href="/new">Create New Page</a>\n            </div>\n            {% for page_id, page in pages.items() %}\n                <div class="page">\n                    <h2><a href="/page/{{ page_id }}">{{ page.title }}</a></h2>\n                    <p>Last modified: {{ page.last_modified }} by {{ page.author }}</p>\n                </div>\n            {% endfor %}\n        </body>\n        </html>\n    '

NEW_PAGE_TEMPLATE = '\n            <!DOCTYPE html>\n            <html>\n            <head>\n                <title>Create New Page</title>\n            </head>\n            <body>\n                <h1>Create New Documentation Page</h1>\n                <form method="POST">\n                    <input type="text" name="page_id" placeholder="Page ID" required><br>\n                    <input type="text" name="title" placeholder="Title" required><br>\n                    <textarea name="content" placeholder="Content (HTML)" required></textarea><br>\n                    <input type="text" name="author" placeholder="Your name" required><br>\n                    <button type="submit">Create Page</button>\n                </form>\n            </body>\n            </html>\n        '

EDIT_PAGE_TEMPLATE = '\n            <!DOCTYPE html>\n            <html>\n            <head>\n                <title>Edit {{ page.title }}</title>\n            </head>\n            <body>\n                <h1>Edit {{ page.title }}</h1>\n                <form method="POST">\n                    <input type="text" name="title" value="{{ page.title }}" required><br>\n                    <textarea name="content" required>{{ page.content }}</textarea><br>\n                    <input type="text" name="author" value="{{ page.author }}" required><br>\n                    <button type="submit">Save Changes</button>\n                </form>\n            </body>\n            </html>\n        '

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = Quart(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _current_timestamp():
    """Return the current time as an ISO 8601 formatted string."""
    return datetime.now().isoformat()


def _build_page_record(form):
    """Build a page record dictionary from submitted form data."""
    return {
        'title': form['title'],
        'content': form['content'],
        'last_modified': _current_timestamp(),
        'author': form['author'],
    }


def _render_documentation_page(page, page_id):
    """Render the full HTML document for a single documentation page."""
    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{page['title']}</title>
        </head>
        <body>
            <h1>{page['title']}</h1>
            <div class="content">
                {page['content']}
            </div>
            <p><small>Last modified: {page['last_modified']} by {page['author']}</small></p>
            <a href="/edit/{page_id}">Edit this page</a> | 
            <a href="/">Back to index</a>
        </body>
        </html>
        """


# ---------------------------------------------------------------------------
# In-memory page store
# ---------------------------------------------------------------------------

documentation_pages = {
    DEFAULT_PAGE_ID: {
        'title': DEFAULT_PAGE_TITLE,
        'content': DEFAULT_PAGE_CONTENT,
        'last_modified': _current_timestamp(),
        'author': DEFAULT_PAGE_AUTHOR,
    },
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
async def index():
    return await render_template_string(INDEX_TEMPLATE, pages=documentation_pages)

@app.route('/page/<page_id>')
async def view_page(page_id):
    if page_id not in documentation_pages:
        return PAGE_NOT_FOUND_RESPONSE
    return _render_documentation_page(documentation_pages[page_id], page_id)

@app.route('/new', methods=['GET', 'POST'])
async def new_page():
    if request.method == 'GET':
        return await render_template_string(NEW_PAGE_TEMPLATE)
    form = await request.form
    page_id = form['page_id']
    documentation_pages[page_id] = _build_page_record(form)
    return redirect(url_for('view_page', page_id=page_id))

@app.route('/edit/<page_id>', methods=['GET', 'POST'])
async def edit_page(page_id):
    if page_id not in documentation_pages:
        return PAGE_NOT_FOUND_RESPONSE
    if request.method == 'GET':
        return await render_template_string(EDIT_PAGE_TEMPLATE, page=documentation_pages[page_id])
    form = await request.form
    documentation_pages[page_id] = _build_page_record(form)
    return redirect(url_for('view_page', page_id=page_id))


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
