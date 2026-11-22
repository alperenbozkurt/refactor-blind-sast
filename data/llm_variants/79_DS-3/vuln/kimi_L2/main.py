from dataclasses import dataclass

import bleach  # noqa: F401  (retained for backwards compatibility)
import markdown
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Application-level configuration values."""

    static_directory: str = 'static'
    templates_directory: str = 'templates'
    static_mount_path: str = '/static'
    static_mount_name: str = 'static'

    notes_template: str = 'notes.html'
    note_detail_template: str = 'note_detail.html'
    note_created_template: str = 'note_created.html'

    index_route: str = '/'
    note_detail_route: str = '/note/{note_id}'
    create_note_route: str = '/note'

    note_not_found_status: int = 404
    note_not_found_detail: str = 'Note not found'


settings = Settings()


# ---------------------------------------------------------------------------
# Template sources
# ---------------------------------------------------------------------------

_NOTES_TEMPLATE = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Notes</title></head>\n        <body>\n            <h1>My Notes</h1>\n            <ul>\n            {% for note in notes %}\n                <li><a href="/note/{{ note.id }}">{{ note.title }}</a></li>\n            {% endfor %}\n            </ul>\n            <form action="/note" method="post">\n                <input type="text" name="title" placeholder="Title">\n                <textarea name="content" placeholder="Content (markdown)"></textarea>\n                <button type="submit">Create Note</button>\n            </form>\n        </body>\n        </html>\n        '

_NOTE_DETAIL_TEMPLATE = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>{{ note.title }}</title></head>\n        <body>\n            <h1>{{ note.title }}</h1>\n            <div class="content">\n                {{ note.content_html|safe }}\n            </div>\n            <a href="/">Back to all notes</a>\n        </body>\n        </html>\n        '

_NOTE_CREATED_TEMPLATE = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Note Created</title></head>\n        <body>\n            <h1>Note Created</h1>\n            <p>Your note "{{ note.title }}" has been created.</p>\n            <a href="/note/{{ note.id }}">View note</a>\n        </body>\n        </html>\n        '


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
app.mount(
    settings.static_mount_path,
    StaticFiles(directory=settings.static_directory),
    name=settings.static_mount_name,
)
templates = Jinja2Templates(directory=settings.templates_directory)

_SEED_NOTES = [
    {'id': 1, 'title': 'Shopping List', 'content': '- Milk\n- Eggs\n- Bread'},
    {'id': 2, 'title': 'TODO', 'content': '1. Fix bug\n2. Write tests'},
]

notes_db = [note.copy() for note in _SEED_NOTES]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def markdown_to_html(md_content):
    return markdown.markdown(md_content)


def _note_with_html(note):
    """Return a copy of ``note`` with its rendered HTML content attached."""
    note_with_html = note.copy()
    note_with_html['content_html'] = markdown_to_html(note['content'])
    return note_with_html


def _find_note(note_id):
    """Return the note with ``note_id`` or ``None`` if it does not exist."""
    for note in notes_db:
        if note['id'] == note_id:
            return note
    return None


def _next_note_id():
    """Compute the id for the next note to be created."""
    return max((note['id'] for note in notes_db)) + 1 if notes_db else 1


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get(settings.index_route, response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_note_with_html(note) for note in notes_db]
    return templates.TemplateResponse(
        settings.notes_template,
        {'request': request, 'notes': notes_with_html},
    )


@app.get(settings.note_detail_route, response_class=HTMLResponse)
async def read_note(request: Request, note_id: int):
    note = _find_note(note_id)
    if note is None:
        raise HTTPException(
            status_code=settings.note_not_found_status,
            detail=settings.note_not_found_detail,
        )
    return templates.TemplateResponse(
        settings.note_detail_template,
        {'request': request, 'note': _note_with_html(note)},
    )


@app.post(settings.create_note_route, response_class=HTMLResponse)
async def create_note(request: Request, title: str=Form(...), content: str=Form(...)):
    new_note = {'id': _next_note_id(), 'title': title, 'content': content}
    notes_db.append(new_note)
    return templates.TemplateResponse(
        settings.note_created_template,
        {'request': request, 'note': new_note},
    )


def get_templates():
    return {
        settings.notes_template: _NOTES_TEMPLATE,
        settings.note_detail_template: _NOTE_DETAIL_TEMPLATE,
        settings.note_created_template: _NOTE_CREATED_TEMPLATE,
    }
