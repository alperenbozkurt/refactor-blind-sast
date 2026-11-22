"""A minimal file-storage web application built with FastAPI.

Uploaded files are stored on disk under ``UPLOAD_DIR`` while their metadata
(filename, description, uploader) is kept in a SQLite database. User-supplied
text is HTML-escaped before being stored so it is safe to render in templates.
"""

import html
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'file_storage.db'
TEMPLATES_DIR = 'templates'
UPLOAD_DIR = 'uploads'
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MiB
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

_CREATE_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS files ('
    'id TEXT PRIMARY KEY, '
    'filename TEXT, '
    'description TEXT, '
    'uploader TEXT, '
    'path TEXT)'
)

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>File Storage</title>
</head>
<body>
    <h1>File Storage System</h1>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" required><br>
        Description: <input type="text" name="description" required><br>
        Your Name: <input type="text" name="uploader" required><br>
        <button type="submit">Upload</button>
    </form>
    <h2>Uploaded Files</h2>
    <ul>
        {% for file in files %}
            <li>
                <a href="/file/{{ file[0] }}">{{ file[1] }}</a>
                (Uploaded by {{ file[3] }})
                <p>{{ file[2] }}</p>
            </li>
        {% endfor %}
    </ul>
</body>
</html>
"""

FILE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ filename }}</title>
</head>
<body>
    <h1>{{ filename }}</h1>
    <p>Uploaded by: {{ uploader }}</p>
    <div>
        <h3>Description:</h3>
        <div>{{ description }}</div>  <!-- Removed | safe filter -->
    </div>
    <a href="/">Back to files</a>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _connect():
    """Open a new connection to the file-metadata database."""
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    """Create the file-metadata table if it does not already exist."""
    conn = _connect()
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    """Persist metadata for an uploaded file.

    The description and uploader name are HTML-escaped before storage so they
    can be rendered back in templates safely.
    """
    sanitized_desc = html.escape(description)
    sanitized_uploader = html.escape(uploader)
    conn = _connect()
    try:
        conn.execute(
            'INSERT INTO files VALUES (?, ?, ?, ?, ?)',
            (file_id, filename, sanitized_desc, sanitized_uploader, path),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_files():
    """Return ``(id, filename, description, uploader)`` rows for all files."""
    conn = _connect()
    try:
        cursor = conn.execute('SELECT id, filename, description, uploader FROM files')
        return cursor.fetchall()
    finally:
        conn.close()


def get_file(file_id: str):
    """Return the full database row for ``file_id``, or ``None`` if missing."""
    conn = _connect()
    try:
        cursor = conn.execute('SELECT * FROM files WHERE id=?', (file_id,))
        return cursor.fetchone()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def is_allowed_file(filename: str):
    """Return True when ``filename`` has one of the allowed extensions."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename: str):
    """Reduce ``filename`` to its basename and replace unsafe characters."""
    filename = Path(filename).name
    return re.sub(r'[^\w\.-]', '_', filename)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    """Render the upload form together with the list of uploaded files."""
    files = get_all_files()
    return templates.TemplateResponse('index.html', {'request': request, 'files': files})


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str = Form(...), uploader: str = Form(...)):
    """Validate, store and register a single uploaded file."""
    if not file:
        raise HTTPException(status_code=400, detail='No file uploaded')
    if not is_allowed_file(file.filename):
        raise HTTPException(status_code=400, detail='File type not allowed')

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_filename = sanitize_filename(file.filename)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f'{file_id}_{safe_filename}')

    try:
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail='File too large')
        with open(file_path, 'wb') as buffer:
            buffer.write(contents)
    except Exception as e:
        # Every failure above (including the size check) is reported as a 500.
        raise HTTPException(status_code=500, detail=str(e))

    save_file_info(file_id, safe_filename, description, uploader, file_path)
    return {'message': 'File uploaded successfully', 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    """Render the metadata page for a single uploaded file."""
    row = get_file(file_id)
    if not row:
        raise HTTPException(status_code=404, detail='File not found')
    return templates.TemplateResponse(
        'file.html',
        {
            'request': request,
            'file_id': row[0],
            'filename': row[1],
            'description': row[2],
            'uploader': row[3],
            'file_path': row[4],
        },
    )


# ---------------------------------------------------------------------------
# Default templates
# ---------------------------------------------------------------------------

def _write_default_templates():
    """(Re)write the bundled Jinja2 templates into the templates directory."""
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    with open(os.path.join(TEMPLATES_DIR, 'index.html'), 'w') as f:
        f.write(INDEX_HTML)
    with open(os.path.join(TEMPLATES_DIR, 'file.html'), 'w') as f:
        f.write(FILE_HTML)


_write_default_templates()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
