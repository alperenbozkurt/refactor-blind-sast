from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown
import bleach

# --------------------------------------------------------------------------- #
# Constants
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

FIRST_NOTE_ID = 1

_NOTES_TEMPLATE_SOURCE = """
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
                <input type="text" name="title" placeholder="Title">
                <textarea name="content" placeholder="Content (markdown)"></textarea>
                <button type="submit">Create Note</button>
            </form>
        </body>
        </html>
        """

_NOTE_DETAIL_TEMPLATE_SOURCE = """
        <!DOCTYPE html>
        <html>
        <head><title>{{ note.title }}</title></head>
        <body>
            <h1>{{ note.title }}</h1>
            <div class="content">
                {{ note.content_html|safe }}
            </div>
            <a href="/">Back to all notes</a>
        </body>
        </html>
        """

_NOTE_CREATED_TEMPLATE_SOURCE = """
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

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

app = FastAPI()
app.mount(STATIC_URL_PATH, StaticFiles(directory=STATIC_DIRECTORY), name=STATIC_MOUNT_NAME)
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)

notes_db = [
    {'id': 1, 'title': 'Shopping List', 'content': '- Milk\n- Eggs\n- Bread'},
    {'id': 2, 'title': 'TODO', 'content': '1. Fix bug\n2. Write tests'},
]

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def markdown_to_html(md_content):
    html = markdown.markdown(md_content)
    return html


def _note_with_html(note):
    """Return a copy of ``note`` including its rendered ``content_html``."""
    rendered = note.copy()
    rendered['content_html'] = markdown_to_html(note['content'])
    return rendered


def _find_note(note_id):
    """Return the first note matching ``note_id`` or ``None``."""
    for note in notes_db:
        if note['id'] == note_id:
            return note
    return None


def _next_note_id():
    if notes_db:
        return max((note['id'] for note in notes_db)) + 1
    return FIRST_NOTE_ID


def _note_not_found():
    return HTTPException(status_code=NOTE_NOT_FOUND_STATUS, detail=NOTE_NOT_FOUND_DETAIL)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get('/', response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_note_with_html(note) for note in notes_db]
    return templates.TemplateResponse(
        NOTES_LIST_TEMPLATE, {'request': request, 'notes': notes_with_html}
    )


@app.get('/note/{note_id}', response_class=HTMLResponse)
async def read_note(request: Request, note_id: int):
    note = _find_note(note_id)
    if note is None:
        raise _note_not_found()
    return templates.TemplateResponse(
        NOTE_DETAIL_TEMPLATE, {'request': request, 'note': _note_with_html(note)}
    )


@app.post('/note', response_class=HTMLResponse)
async def create_note(request: Request, title: str=Form(...), content: str=Form(...)):
    new_note = {'id': _next_note_id(), 'title': title, 'content': content}
    notes_db.append(new_note)
    return templates.TemplateResponse(
        NOTE_CREATED_TEMPLATE, {'request': request, 'note': new_note}
    )


def get_templates():
    return {
        NOTES_LIST_TEMPLATE: _NOTES_TEMPLATE_SOURCE,
        NOTE_DETAIL_TEMPLATE: _NOTE_DETAIL_TEMPLATE_SOURCE,
        NOTE_CREATED_TEMPLATE: _NOTE_CREATED_TEMPLATE_SOURCE,
    }
