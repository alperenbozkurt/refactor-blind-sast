"""Markdown notes web application.

A small FastAPI service that keeps notes in memory, renders their Markdown
content to sanitized HTML and lets users create new notes via an HTML form.
The module is organised into configuration, rendering/sanitisation helpers,
note-store helpers, HTTP routes and embedded template sources.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import bleach
import markdown
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Notes are plain dicts so they can be passed straight to the Jinja2 templates.
Note = Dict[str, Any]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Static wiring, template names and error messaging for the app."""

    static_url_path: str = '/static'
    static_directory: str = 'static'
    static_mount_name: str = 'static'
    templates_directory: str = 'templates'
    notes_template: str = 'notes.html'
    note_detail_template: str = 'note_detail.html'
    note_created_template: str = 'note_created.html'
    note_not_found_status: int = 404
    note_not_found_detail: str = 'Note not found'
    first_note_id: int = 1


settings = Settings()

# Markup that is allowed to survive sanitisation of rendered Markdown.
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

# Key under which the rendered HTML of a note is exposed to the templates.
CONTENT_HTML_FIELD = 'content_html'

SEED_NOTES: List[Note] = [
    {'id': 1, 'title': 'Shopping List', 'content': '- Milk\n- Eggs\n- Bread'},
    {'id': 2, 'title': 'TODO', 'content': '1. Fix bug\n2. Write tests'},
]

# In-memory note store; starts from a copy of the seed data.
notes_db: List[Note] = [dict(note) for note in SEED_NOTES]


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
app.mount(
    settings.static_url_path,
    StaticFiles(directory=settings.static_directory),
    name=settings.static_mount_name,
)
templates = Jinja2Templates(directory=settings.templates_directory)


# ---------------------------------------------------------------------------
# Rendering and sanitisation helpers
# ---------------------------------------------------------------------------

def _render_markdown(md_content: str) -> str:
    """Convert Markdown source into raw HTML."""
    return markdown.markdown(md_content)


def _sanitize_html(html: str) -> str:
    """Strip disallowed tags and attributes from rendered HTML."""
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)


def _sanitize_text(text: str) -> str:
    """Strip all HTML markup from untrusted plain text."""
    return bleach.clean(text, strip=True)


def markdown_to_html(md_content):
    """Render Markdown content into safe, sanitized HTML."""
    return _sanitize_html(_render_markdown(md_content))


# ---------------------------------------------------------------------------
# Note-store helpers
# ---------------------------------------------------------------------------

def _note_with_html(note: Note) -> Note:
    """Return a copy of ``note`` augmented with rendered HTML content."""
    note_with_html = note.copy()
    note_with_html[CONTENT_HTML_FIELD] = markdown_to_html(note['content'])
    return note_with_html


def _find_note(note_id: int) -> Optional[Note]:
    """Return the note with the given id, or ``None`` when it is missing."""
    for note in notes_db:
        if note['id'] == note_id:
            return note
    return None


def _next_note_id() -> int:
    """Return the id to assign to the next note that gets created."""
    return max((note['id'] for note in notes_db)) + 1 if notes_db else settings.first_note_id


def _build_note(title: str, content: str) -> Note:
    """Build a new sanitized note record with a freshly allocated id."""
    return {
        'id': _next_note_id(),
        'title': _sanitize_text(title),
        'content': _sanitize_text(content),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/', response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_note_with_html(note) for note in notes_db]
    return templates.TemplateResponse(
        settings.notes_template,
        {'request': request, 'notes': notes_with_html},
    )


@app.get('/note/{note_id}', response_class=HTMLResponse)
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


@app.post('/note', response_class=HTMLResponse)
async def create_note(request: Request, title: str = Form(...), content: str = Form(...)):
    new_note = _build_note(title, content)
    notes_db.append(new_note)
    return templates.TemplateResponse(
        settings.note_created_template,
        {'request': request, 'note': new_note},
    )


# ---------------------------------------------------------------------------
# Embedded template sources
# ---------------------------------------------------------------------------

_NOTES_PAGE_TEMPLATE = '''
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
        '''

_NOTE_DETAIL_PAGE_TEMPLATE = '''
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
        '''

_NOTE_CREATED_PAGE_TEMPLATE = '''
        <!DOCTYPE html>
        <html>
        <head><title>Note Created</title></head>
        <body>
            <h1>Note Created</h1>
            <p>Your note "{{ note.title }}" has been created.</p>
            <a href="/note/{{ note.id }}">View note</a>
        </body>
        </html>
        '''


def get_templates():
    """Return the embedded template sources keyed by template name."""
    return {
        settings.notes_template: _NOTES_PAGE_TEMPLATE,
        settings.note_detail_template: _NOTE_DETAIL_PAGE_TEMPLATE,
        settings.note_created_template: _NOTE_CREATED_PAGE_TEMPLATE,
    }
