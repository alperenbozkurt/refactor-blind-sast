from fastapi import FastAPI, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sqlite3
import uuid
from contextlib import contextmanager
from typing import List
from pathlib import Path
import html
import re

# --------------------------------------------------------------------------- #
# Configuration constants
# --------------------------------------------------------------------------- #
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_DIR = 'uploads'

DB_PATH = 'file_storage.db'
STATIC_DIR = 'static'
STATIC_URL_PATH = '/static'
TEMPLATES_DIR = 'templates'
INDEX_TEMPLATE_NAME = 'index.html'
FILE_TEMPLATE_NAME = 'file.html'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

UNSAFE_FILENAME_CHARS = re.compile(r'[^\w\.-]')

CREATE_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS files\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 filename TEXT,\n'
    '                 description TEXT,\n'
    '                 uploader TEXT,\n'
    '                 path TEXT)'
)
INSERT_FILE_SQL = 'INSERT INTO files VALUES (?, ?, ?, ?, ?)'
SELECT_ALL_FILES_SQL = 'SELECT id, filename, description, uploader FROM files'
SELECT_FILE_BY_ID_SQL = 'SELECT * FROM files WHERE id=?'

INDEX_TEMPLATE_HTML = '''
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
'''

FILE_TEMPLATE_HTML = '''
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
'''

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = FastAPI()
app.mount(STATIC_URL_PATH, StaticFiles(directory=STATIC_DIR), name='static')
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
@contextmanager
def _db_cursor(commit: bool = False):
    """Yield a cursor on a fresh connection; always close the connection."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn.cursor()
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db():
    with _db_cursor(commit=True) as c:
        c.execute(CREATE_TABLE_SQL)


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    sanitized_desc = html.escape(description)
    sanitized_uploader = html.escape(uploader)
    with _db_cursor(commit=True) as c:
        c.execute(INSERT_FILE_SQL, (file_id, filename, sanitized_desc, sanitized_uploader, path))


def get_all_files():
    with _db_cursor() as c:
        c.execute(SELECT_ALL_FILES_SQL)
        files = c.fetchall()
    return files


def get_file(file_id: str):
    with _db_cursor() as c:
        c.execute(SELECT_FILE_BY_ID_SQL, (file_id,))
        file = c.fetchone()
    return file


# --------------------------------------------------------------------------- #
# File helpers
# --------------------------------------------------------------------------- #
def is_allowed_file(filename: str):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename: str):
    filename = Path(filename).name
    return UNSAFE_FILENAME_CHARS.sub('_', filename)


def _build_upload_path(file_id: str, safe_filename: str) -> str:
    return os.path.join(UPLOAD_DIR, f'{file_id}_{safe_filename}')


async def _store_upload(file: UploadFile, file_path: str) -> None:
    """Read the upload, enforce the size limit and write it to disk."""
    try:
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail='File too large')
        with open(file_path, 'wb') as buffer:
            buffer.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return templates.TemplateResponse(INDEX_TEMPLATE_NAME, {'request': request, 'files': files})


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str=Form(...), uploader: str=Form(...)):
    if not file:
        raise HTTPException(status_code=400, detail='No file uploaded')
    if not is_allowed_file(file.filename):
        raise HTTPException(status_code=400, detail='File type not allowed')
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_filename = sanitize_filename(file.filename)
    file_id = str(uuid.uuid4())
    file_path = _build_upload_path(file_id, safe_filename)
    await _store_upload(file, file_path)
    save_file_info(file_id, safe_filename, description, uploader, file_path)
    return {'message': 'File uploaded successfully', 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail='File not found')
    return templates.TemplateResponse(
        FILE_TEMPLATE_NAME,
        {
            'request': request,
            'file_id': file[0],
            'filename': file[1],
            'description': file[2],
            'uploader': file[3],
            'file_path': file[4],
        },
    )


# --------------------------------------------------------------------------- #
# Template bootstrapping
# --------------------------------------------------------------------------- #
def _write_template(name: str, content: str) -> None:
    with open(f'{TEMPLATES_DIR}/{name}', 'w') as template_file:
        template_file.write(content)


def write_templates() -> None:
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    _write_template(INDEX_TEMPLATE_NAME, INDEX_TEMPLATE_HTML)
    _write_template(FILE_TEMPLATE_NAME, FILE_TEMPLATE_HTML)


write_templates()


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
