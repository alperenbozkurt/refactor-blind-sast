from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown
import bleach

# --------------------------------------------------------------------------- #
# Configuration constants
# --------------------------------------------------------------------------- #
STATIC_URL_PATH = '/static'
STATIC_DIRECTORY = 'static'
STATIC_MOUNT_NAME = 'static'
TEMPLATES_DIRECTORY = 'templates'

NOTES_LIST_TEMPLATE = 'notes.html'
NOTE_DETAIL_TEMPLATE = 'note_detail.html'
NOTE_CREATED_TEMPLATE = 'note_created.html'

NOTE_NOT_FOUND_STATUS = 404
NOTE_NOT_FOUND_DETAIL = 'Note not found'

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = FastAPI()
app.mount(STATIC_URL_PATH, StaticFiles(directory=STATIC_DIRECTORY), name=STATIC_MOUNT_NAME)
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)

# --------------------------------------------------------------------------- #
# Sanitisation settings
# --------------------------------------------------------------------------- #
ALLOWED_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'b', 'i', 'strong', 'em', 'tt', 'p', 'br', 'span', 'div', 'blockquote', 'code', 'pre', 'hr', 'ul', 'ol', 'li', 'dd', 'dt', 'a', 'img']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title'], 'img': ['src', 'alt', 'title']}

# --------------------------------------------------------------------------- #
# In-memory data store
# --------------------------------------------------------------------------- #
notes_db = [{'id': 1, 'title': 'Shopping List', 'content': '- Milk\n- Eggs\n- Bread'}, {'id': 2, 'title': 'TODO', 'content': '1. Fix bug\n2. Write tests'}]

# --------------------------------------------------------------------------- #
# Template sources
# --------------------------------------------------------------------------- #
NOTES_LIST_TEMPLATE_SOURCE = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Notes</title></head>\n        <body>\n            <h1>My Notes</h1>\n            <ul>\n            {% for note in notes %}\n                <li><a href="/note/{{ note.id }}">{{ note.title }}</a></li>\n            {% endfor %}\n            </ul>\n            <form action="/note" method="post">\n                <input type="text" name="title" placeholder="Title" required>\n                <textarea name="content" placeholder="Content (markdown)" required></textarea>\n                <button type="submit">Create Note</button>\n            </form>\n        </body>\n        </html>\n        '

NOTE_DETAIL_TEMPLATE_SOURCE = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>{{ note.title }}</title></head>\n        <body>\n            <h1>{{ note.title }}</h1>\n            <div class="content">\n                {{ note.content_html }}\n            </div>\n            <a href="/">Back to all notes</a>\n        </body>\n        </html>\n        '

NOTE_CREATED_TEMPLATE_SOURCE = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Note Created</title></head>\n        <body>\n            <h1>Note Created</h1>\n            <p>Your note "{{ note.title }}" has been created.</p>\n            <a href="/note/{{ note.id }}">View note</a>\n        </body>\n        </html>\n        '


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def markdown_to_html(md_content):
    html = markdown.markdown(md_content)
    clean_html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    return clean_html


def _sanitize_text(text):
    """Strip all disallowed markup from user-supplied plain text."""
    return bleach.clean(text, strip=True)


def _note_with_html(note):
    """Return a copy of ``note`` including its rendered, sanitised HTML."""
    rendered = note.copy()
    rendered['content_html'] = markdown_to_html(note['content'])
    return rendered


def _find_note(note_id):
    """Return the note with the given id, or ``None`` if absent."""
    for note in notes_db:
        if note['id'] == note_id:
            return note
    return None


def _next_note_id():
    """Compute the id for a newly created note."""
    return max((note['id'] for note in notes_db)) + 1 if notes_db else 1


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get('/', response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_note_with_html(note) for note in notes_db]
    return templates.TemplateResponse(NOTES_LIST_TEMPLATE, {'request': request, 'notes': notes_with_html})


@app.get('/note/{note_id}', response_class=HTMLResponse)
async def read_note(request: Request, note_id: int):
    note = _find_note(note_id)
    if note is not None:
        return templates.TemplateResponse(NOTE_DETAIL_TEMPLATE, {'request': request, 'note': _note_with_html(note)})
    raise HTTPException(status_code=NOTE_NOT_FOUND_STATUS, detail=NOTE_NOT_FOUND_DETAIL)


@app.post('/note', response_class=HTMLResponse)
async def create_note(request: Request, title: str=Form(...), content: str=Form(...)):
    clean_title = _sanitize_text(title)
    clean_content = _sanitize_text(content)
    new_id = _next_note_id()
    new_note = {'id': new_id, 'title': clean_title, 'content': clean_content}
    notes_db.append(new_note)
    return templates.TemplateResponse(NOTE_CREATED_TEMPLATE, {'request': request, 'note': new_note})


def get_templates():
    return {
        NOTES_LIST_TEMPLATE: NOTES_LIST_TEMPLATE_SOURCE,
        NOTE_DETAIL_TEMPLATE: NOTE_DETAIL_TEMPLATE_SOURCE,
        NOTE_CREATED_TEMPLATE: NOTE_CREATED_TEMPLATE_SOURCE,
    }
