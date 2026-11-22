from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown
import bleach

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

notes_db = [
    {'id': 1, 'title': 'Shopping List', 'content': '- Milk\n- Eggs\n- Bread'},
    {'id': 2, 'title': 'TODO', 'content': '1. Fix bug\n2. Write tests'},
]


def markdown_to_html(md_content):
    return markdown.markdown(md_content)


def _with_html(note):
    """Return a copy of the note with its rendered markdown under 'content_html'."""
    rendered = note.copy()
    rendered['content_html'] = markdown_to_html(note['content'])
    return rendered


@app.get('/', response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_with_html(note) for note in notes_db]
    return templates.TemplateResponse(
        'notes.html', {'request': request, 'notes': notes_with_html}
    )


@app.get('/note/{note_id}', response_class=HTMLResponse)
async def read_note(request: Request, note_id: int):
    for note in notes_db:
        if note['id'] == note_id:
            return templates.TemplateResponse(
                'note_detail.html', {'request': request, 'note': _with_html(note)}
            )
    raise HTTPException(status_code=404, detail='Note not found')


@app.post('/note', response_class=HTMLResponse)
async def create_note(request: Request, title: str = Form(...), content: str = Form(...)):
    new_id = max(note['id'] for note in notes_db) + 1 if notes_db else 1
    new_note = {'id': new_id, 'title': title, 'content': content}
    notes_db.append(new_note)
    return templates.TemplateResponse(
        'note_created.html', {'request': request, 'note': new_note}
    )


def get_templates():
    return {
        'notes.html': '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Notes</title></head>\n        <body>\n            <h1>My Notes</h1>\n            <ul>\n            {% for note in notes %}\n                <li><a href="/note/{{ note.id }}">{{ note.title }}</a></li>\n            {% endfor %}\n            </ul>\n            <form action="/note" method="post">\n                <input type="text" name="title" placeholder="Title">\n                <textarea name="content" placeholder="Content (markdown)"></textarea>\n                <button type="submit">Create Note</button>\n            </form>\n        </body>\n        </html>\n        ',
        'note_detail.html': '\n        <!DOCTYPE html>\n        <html>\n        <head><title>{{ note.title }}</title></head>\n        <body>\n            <h1>{{ note.title }}</h1>\n            <div class="content">\n                {{ note.content_html|safe }}\n            </div>\n            <a href="/">Back to all notes</a>\n        </body>\n        </html>\n        ',
        'note_created.html': '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Note Created</title></head>\n        <body>\n            <h1>Note Created</h1>\n            <p>Your note "{{ note.title }}" has been created.</p>\n            <a href="/note/{{ note.id }}">View note</a>\n        </body>\n        </html>\n        ',
    }
