"""A simple in-memory documentation system built with Quart."""

from quart import Quart, request, render_template_string, redirect, url_for
from datetime import datetime
import bleach
import hashlib

app = Quart(__name__)

documentation_pages = {
    'home': {
        'title': 'Welcome',
        'content': '<p>Welcome to our documentation system</p>',
        'last_modified': datetime.now().isoformat(),
        'author': 'admin',
    },
}

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

PAGE_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
        </head>
        <body>
            <h1>{title}</h1>
            <div class="content">
                {content}
            </div>
            <p><small>Last modified: {last_modified} by {author}</small></p>
            <a href="/edit/{page_id}">Edit this page</a> | 
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

NOT_FOUND_RESPONSE = ('Page not found', 404)


def _page_from_form(form):
    """Build a page record from submitted form data."""
    return {
        'title': form['title'],
        'content': form['content'],
        'last_modified': datetime.now().isoformat(),
        'author': form['author'],
    }


@app.route('/')
async def index():
    return await render_template_string(INDEX_TEMPLATE, pages=documentation_pages)


@app.route('/page/<page_id>')
async def view_page(page_id):
    if page_id not in documentation_pages:
        return NOT_FOUND_RESPONSE
    page = documentation_pages[page_id]
    return PAGE_TEMPLATE.format(
        page_id=page_id,
        title=page['title'],
        content=page['content'],
        last_modified=page['last_modified'],
        author=page['author'],
    )


@app.route('/new', methods=['GET', 'POST'])
async def new_page():
    if request.method == 'GET':
        return await render_template_string(NEW_PAGE_TEMPLATE)
    form = await request.form
    page_id = form['page_id']
    documentation_pages[page_id] = _page_from_form(form)
    return redirect(url_for('view_page', page_id=page_id))


@app.route('/edit/<page_id>', methods=['GET', 'POST'])
async def edit_page(page_id):
    if page_id not in documentation_pages:
        return NOT_FOUND_RESPONSE
    if request.method == 'GET':
        return await render_template_string(
            EDIT_PAGE_TEMPLATE, page=documentation_pages[page_id]
        )
    form = await request.form
    documentation_pages[page_id] = _page_from_form(form)
    return redirect(url_for('view_page', page_id=page_id))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
