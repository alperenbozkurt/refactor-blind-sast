from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown
import bleach

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

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

notes_db = [
    {'id': 1, 'title': 'Shopping List', 'content': '- Milk\n- Eggs\n- Bread'},
    {'id': 2, 'title': 'TODO', 'content': '1. Fix bug\n2. Write tests'},
]


def markdown_to_html(md_content):
    """Convert markdown to sanitized HTML."""
    html = markdown.markdown(md_content)
    return bleach.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
    )


def _note_with_html(note):
    """Return a copy of the note with its content rendered as HTML."""
    note_copy = note.copy()
    note_copy['content_html'] = markdown_to_html(note['content'])
    return note_copy


@app.get('/', response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_note_with_html(note) for note in notes_db]
    return templates.TemplateResponse(
        'notes.html', {'request': request, 'notes': notes_with_html}
    )


@app.get('/note/{note_id}', response_class=HTMLResponse)
async def read_note(request: Request, note_id: int):
    note = next((n for n in notes_db if n['id'] == note_id), None)
    if note is None:
        raise HTTPException(status_code=404, detail='Note not found')
    return templates.TemplateResponse(
        'note_detail.html', {'request': request, 'note': _note_with_html(note)}
    )


@app.post('/note', response_class=HTMLResponse)
async def create_note(request: Request, title: str = Form(...), content: str = Form(...)):
    new_note = {
        'id': max((note['id'] for note in notes_db), default=0) + 1,
        'title': bleach.clean(title, strip=True),
        'content': bleach.clean(content, strip=True),
    }
    notes_db.append(new_note)
    return templates.TemplateResponse(
        'note_created.html', {'request': request, 'note': new_note}
    )


def get_templates():
    return {
        'notes.html': '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Notes</title></head>\n        <body>\n            <h1>My Notes</h1>\n            <ul>\n            {% for note in notes %}\n                <li><a href="/note/{{ note.id }}">{{ note.title }}</a></li>\n            {% endfor %}\n            </ul>\n            <form action="/note" method="post">\n                <input type="text" name="title" placeholder="Title" required>\n                <textarea name="content" placeholder="Content (markdown)" required></textarea>\n                <button type="submit">Create Note</button>\n            </form>\n        </body>\n        </html>\n        ',
        'note_detail.html': '\n        <!DOCTYPE html>\n        <html>\n        <head><title>{{ note.title }}</title></head>\n        <body>\n            <h1>{{ note.title }}</h1>\n            <div class="content">\n                {{ note.content_html }}\n            </div>\n            <a href="/">Back to all notes</a>\n        </body>\n        </html>\n        ',
        'note_created.html': '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Note Created</title></head>\n        <body>\n            <h1>Note Created</h1>\n            <p>Your note "{{ note.title }}" has been created.</p>\n            <a href="/note/{{ note.id }}">View note</a>\n        </body>\n        </html>\n        ',
    }
