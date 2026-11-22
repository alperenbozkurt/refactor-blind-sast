"""A small in-memory HTML documentation system built with Quart.

Page content is sanitized with Bleach before being stored and rendered.
"""

import hashlib  # noqa: F401  (kept for backwards compatibility)
from dataclasses import dataclass
from datetime import datetime

import bleach
from quart import Quart, redirect, render_template_string, request, url_for

# ---------------------------------------------------------------------------
# Sanitization settings
# ---------------------------------------------------------------------------

ALLOWED_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'b', 'i', 'strong', 'em',
    'a', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'hr', 'img',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
}

# ---------------------------------------------------------------------------
# HTML templates (kept byte-for-byte identical to the original inline strings)
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Documentation System</title>
            <style>
                .page { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
                .actions { margin: 20px 0; }
            </style>
        </head>
        <body>
            <h1>Documentation Pages</h1>
            <div class="actions">
                <a href="/new">Create New Page</a>
            </div>
            {% for page_id, page in pages.items() %}
                <div class="page">
                    <h2><a href="/page/{{ page_id }}">{{ page.title }}</a></h2>
                    <p>Last modified: {{ page.last_modified }} by {{ page.author }}</p>
                </div>
            {% endfor %}
        </body>
        </html>
    """

VIEW_PAGE_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ page.title }}</title>
        </head>
        <body>
            <h1>{{ page.title }}</h1>
            <div class="content">
                {{ page.content|safe }}
            </div>
            <p><small>Last modified: {{ page.last_modified }} by {{ page.author }}</small></p>
            <a href="/edit/{{ page_id }}">Edit this page</a> | 
            <a href="/">Back to index</a>
        </body>
        </html>
    """

NEW_PAGE_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Create New Page</title>
            </head>
            <body>
                <h1>Create New Documentation Page</h1>
                <form method="POST">
                    <input type="text" name="page_id" placeholder="Page ID" required><br>
                    <input type="text" name="title" placeholder="Title" required><br>
                    <textarea name="content" placeholder="Content (HTML)" required></textarea><br>
                    <input type="text" name="author" placeholder="Your name" required><br>
                    <button type="submit">Create Page</button>
                </form>
            </body>
            </html>
        """

EDIT_PAGE_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Edit {{ page.title }}</title>
            </head>
            <body>
                <h1>Edit {{ page.title }}</h1>
                <form method="POST">
                    <input type="text" name="title" value="{{ page.title }}" required><br>
                    <textarea name="content" required>{{ page.content }}</textarea><br>
                    <input type="text" name="author" value="{{ page.author }}" required><br>
                    <button type="submit">Save Changes</button>
                </form>
            </body>
            </html>
        """

# ---------------------------------------------------------------------------
# Other constants
# ---------------------------------------------------------------------------

PAGE_NOT_FOUND_RESPONSE = ('Page not found', 404)


@dataclass(frozen=True)
class ServerConfig:
    """Options used when running the built-in development server."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


SERVER_CONFIG = ServerConfig()

app = Quart(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def sanitize_content(content):
    """Clean rich-text HTML, keeping only whitelisted tags and attributes."""
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )


def _sanitize_plain_text(text):
    """Strip all HTML markup from a plain-text value."""
    return bleach.clean(text, strip=True)


def _current_timestamp():
    """Return the current time as an ISO-8601 string."""
    return datetime.now().isoformat()


def _build_page(title, content, author):
    """Build a sanitized page record for storage."""
    return {
        'title': _sanitize_plain_text(title),
        'content': sanitize_content(content),
        'last_modified': _current_timestamp(),
        'author': _sanitize_plain_text(author),
    }


def _save_page(page_id, title, content, author):
    """Create or replace the page stored under ``page_id``."""
    documentation_pages[page_id] = _build_page(title, content, author)


# ---------------------------------------------------------------------------
# Page storage
# ---------------------------------------------------------------------------

documentation_pages = {
    'home': {
        'title': 'Welcome',
        'content': '<p>Welcome to our documentation system</p>',
        'last_modified': _current_timestamp(),
        'author': 'admin',
    },
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
async def index():
    """Render the index listing all documentation pages."""
    return await render_template_string(INDEX_TEMPLATE, pages=documentation_pages)


@app.route('/page/<page_id>')
async def view_page(page_id):
    """Render a single documentation page."""
    if page_id not in documentation_pages:
        return PAGE_NOT_FOUND_RESPONSE
    page = documentation_pages[page_id]
    return await render_template_string(VIEW_PAGE_TEMPLATE, page=page)


@app.route('/new', methods=['GET', 'POST'])
async def new_page():
    """Show the create-page form, or create a new page on submission."""
    if request.method == 'GET':
        return await render_template_string(NEW_PAGE_TEMPLATE)
    form = await request.form
    page_id = form['page_id']
    _save_page(
        page_id,
        title=form['title'],
        content=form['content'],
        author=form['author'],
    )
    return redirect(url_for('view_page', page_id=page_id))


@app.route('/edit/<page_id>', methods=['GET', 'POST'])
async def edit_page(page_id):
    """Show the edit form, or save changes to an existing page."""
    if page_id not in documentation_pages:
        return PAGE_NOT_FOUND_RESPONSE
    if request.method == 'GET':
        page = documentation_pages[page_id]
        return await render_template_string(EDIT_PAGE_TEMPLATE, page=page)
    form = await request.form
    _save_page(
        page_id,
        title=form['title'],
        content=form['content'],
        author=form['author'],
    )
    return redirect(url_for('view_page', page_id=page_id))


if __name__ == '__main__':
    app.run(
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )
