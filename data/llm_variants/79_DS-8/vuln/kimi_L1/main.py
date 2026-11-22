"""Minimal Quart-based documentation system.

Pages are stored in the in-memory ``documentation_pages`` mapping and can be
listed, viewed, created, and edited through the routes defined below.
"""

from datetime import datetime

import bleach  # noqa: F401  # Unused, kept to preserve the module's public names.
import hashlib  # noqa: F401  # Unused, kept to preserve the module's public names.
from quart import Quart, redirect, render_template_string, request, url_for

app = Quart(__name__)

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

documentation_pages = {
    'home': {
        'title': 'Welcome',
        'content': '<p>Welcome to our documentation system</p>',
        'last_modified': datetime.now().isoformat(),
        'author': 'admin',
    },
}


def _build_page_record(form):
    """Build a page record dict from submitted form data."""
    return {
        'title': form['title'],
        'content': form['content'],
        'last_modified': datetime.now().isoformat(),
        'author': form['author'],
    }


@app.route('/')
async def index():
    """Render the index listing all documentation pages."""
    return await render_template_string(INDEX_TEMPLATE, pages=documentation_pages)


@app.route('/page/<page_id>')
async def view_page(page_id):
    """Render a single documentation page, or 404 if it does not exist."""
    if page_id not in documentation_pages:
        return ('Page not found', 404)

    def render_documentation_page(page):
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

    return render_documentation_page(documentation_pages[page_id])


@app.route('/new', methods=['GET', 'POST'])
async def new_page():
    """Show the create-page form on GET, or create a new page on POST."""
    if request.method == 'GET':
        return await render_template_string(NEW_PAGE_TEMPLATE)

    form = await request.form
    page_id = form['page_id']
    documentation_pages[page_id] = _build_page_record(form)
    return redirect(url_for('view_page', page_id=page_id))


@app.route('/edit/<page_id>', methods=['GET', 'POST'])
async def edit_page(page_id):
    """Show the edit form on GET, or save changes to the page on POST."""
    if page_id not in documentation_pages:
        return ('Page not found', 404)

    if request.method == 'GET':
        return await render_template_string(
            EDIT_PAGE_TEMPLATE, page=documentation_pages[page_id]
        )

    form = await request.form
    documentation_pages[page_id] = _build_page_record(form)
    return redirect(url_for('view_page', page_id=page_id))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
