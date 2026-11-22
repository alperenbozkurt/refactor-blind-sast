from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown
import bleach

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

notes_db = [
    {"id": 1, "title": "Shopping List", "content": "- Milk\n- Eggs\n- Bread"},
    {"id": 2, "title": "TODO", "content": "1. Fix bug\n2. Write tests"},
]


def markdown_to_html(md_content):
    return markdown.markdown(md_content)


def _note_with_html(note):
    note_with_html = note.copy()
    note_with_html["content_html"] = markdown_to_html(note["content"])
    return note_with_html


@app.get("/", response_class=HTMLResponse)
async def read_notes(request: Request):
    notes_with_html = [_note_with_html(note) for note in notes_db]
    return templates.TemplateResponse(
        "notes.html", {"request": request, "notes": notes_with_html}
    )


@app.get("/note/{note_id}", response_class=HTMLResponse)
async def read_note(request: Request, note_id: int):
    note = next((n for n in notes_db if n["id"] == note_id), None)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return templates.TemplateResponse(
        "note_detail.html", {"request": request, "note": _note_with_html(note)}
    )


@app.post("/note", response_class=HTMLResponse)
async def create_note(
    request: Request, title: str = Form(...), content: str = Form(...)
):
    new_id = max((note["id"] for note in notes_db), default=0) + 1
    new_note = {"id": new_id, "title": title, "content": content}
    notes_db.append(new_note)
    return templates.TemplateResponse(
        "note_created.html", {"request": request, "note": new_note}
    )


def get_templates():
    return {
        "notes.html": """
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
        </html>\n        """,
        "note_detail.html": """
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
        </html>\n        """,
        "note_created.html": """
        <!DOCTYPE html>
        <html>
        <head><title>Note Created</title></head>
        <body>
            <h1>Note Created</h1>
            <p>Your note "{{ note.title }}" has been created.</p>
            <a href="/note/{{ note.id }}">View note</a>
        </body>
        </html>\n        """,
    }
