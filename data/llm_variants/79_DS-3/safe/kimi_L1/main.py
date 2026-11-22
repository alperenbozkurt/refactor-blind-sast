"""A simple FastAPI application for creating and viewing Markdown notes."""

import bleach
import markdown
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Whitelists used to sanitize the rendered Markdown.
ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'b', 'i', 'strong', 'em', 'tt',
    'p', 'br', 'span', 'div', 'blockquote',
    'code', 'pre', 'hr',
    'ul', 'ol', 'li', 'dd', 'dt',
    'a', 'img',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
}

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

# In-memory note storage.
notes_db = [
    {'id': 1, 'title': 'Shopping List', 'content': '- Milk\n- Eggs\n- Bread'},
    {'id': 2, 'title': 'TODO', 'content': '1. Fix bug\n2. Write tests'},
]


def markdown_to_html(md_content):
    """Render Markdown content to sanitized HTML."""
    html = markdown.markdown(md_content)
    return bleach.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
    )


def _note_with_html(note):
    """Return a copy of a note with its content rendered as HTML."""
    note_with_html = note.copy()
    note_with_html['content_html'] = markdown_to_html(note['content'])
    return note_with_html


@app.get('/', response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_note_with_html(note) for note in notes_db]
    return templates.TemplateResponse(
        'notes.html', {'request': request, 'notes': notes_with_html}
    )


@app.get('/note/{note_id}', response_class=HTMLResponse)
async def read_note(request: Request, note_id: int):
    for note in notes_db:
        if note['id'] == note_id:
            return templates.TemplateResponse(
                'note_detail.html',
                {'request': request, 'note': _note_with_html(note)},
            )
    raise HTTPException(status_code=404, detail='Note not found')


@app.post('/note', response_class=HTMLResponse)
async def create_note(
    request: Request, title: str = Form(...), content: str = Form(...)
):
    clean_title = bleach.clean(title, strip=True)
    clean_content = bleach.clean(content, strip=True)
    new_id = max(note['id'] for note in notes_db) + 1 if notes_db else 1
    new_note = {'id': new_id, 'title': clean_title, 'content': clean_content}
    notes_db.append(new_note)
    return templates.TemplateResponse(
        'note_created.html', {'request': request, 'note': new_note}
    )


_NOTES_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head><title>Notes</title></head>
        <body>
            <h1>My Notes</h1>
            <ul>
            {% for note in notes %}
                <li><a href="/note/{{ note.id }}">{{ note.title }}</a></li>
            {% endfor %}
            </ul>
            <form action="/note" method="post">
                <input type="text" name="title" placeholder="Title" required>
                <textarea name="content" placeholder="Content (markdown)" required></textarea>
                <button type="submit">Create Note</button>
            </form>
        </body>
        </html>
        """

_NOTE_DETAIL_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head><title>{{ note.title }}</title></head>
        <body>
            <h1>{{ note.title }}</h1>
            <div class="content">
                {{ note.content_html }}
            </div>
            <a href="/">Back to all notes</a>
        </body>
        </html>
        """

_NOTE_CREATED_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head><title>Note Created</title></head>
        <body>
            <h1>Note Created</h1>
            <p>Your note "{{ note.title }}" has been created.</p>
            <a href="/note/{{ note.id }}">View note</a>
        </body>
        </html>
        """


def get_templates():
    """Return the application's HTML templates keyed by template name."""
    return {
        'notes.html': _NOTES_TEMPLATE,
        'note_detail.html': _NOTE_DETAIL_TEMPLATE,
        'note_created.html': _NOTE_CREATED_TEMPLATE,
    }
