from fastapi import FastAPI, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sqlite3
import uuid
from contextlib import contextmanager
from typing import List

# --------------------------------------------------------------------------- #
# Configuration constants
# --------------------------------------------------------------------------- #
DB_PATH = 'file_storage.db'
UPLOAD_DIR = 'uploads'
STATIC_DIR = 'static'
STATIC_URL = '/static'
TEMPLATES_DIR = 'templates'
INDEX_TEMPLATE_NAME = 'index.html'
FILE_TEMPLATE_NAME = 'file.html'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

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

INDEX_TEMPLATE_HTML = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>File Storage</title>\n</head>\n<body>\n    <h1>File Storage System</h1>\n    <form action="/upload" method="post" enctype="multipart/form-data">\n        <input type="file" name="file" required><br>\n        Description: <input type="text" name="description" required><br>\n        Your Name: <input type="text" name="uploader" required><br>\n        <button type="submit">Upload</button>\n    </form>\n    <h2>Uploaded Files</h2>\n    <ul>\n        {% for file in files %}\n            <li>\n                <a href="/file/{{ file[0] }}">{{ file[1] }}</a>\n                (Uploaded by {{ file[3] }})\n                <p>{{ file[2] }}</p>\n            </li>\n        {% endfor %}\n    </ul>\n</body>\n</html>\n'

FILE_TEMPLATE_HTML = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>{{ filename }}</title>\n</head>\n<body>\n    <h1>{{ filename }}</h1>\n    <p>Uploaded by: {{ uploader }}</p>\n    <div>\n        <h3>Description:</h3>\n        <div>{{ description | safe }}</div>\n    </div>\n    <a href="/">Back to files</a>\n</body>\n</html>\n'

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = FastAPI()
app.mount(STATIC_URL, StaticFiles(directory=STATIC_DIR), name='static')
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
@contextmanager
def _db_connection():
    """Yield a SQLite connection and always close it afterwards."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with _db_connection() as conn:
        c = conn.cursor()
        c.execute(CREATE_TABLE_SQL)
        conn.commit()


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    with _db_connection() as conn:
        c = conn.cursor()
        c.execute(INSERT_FILE_SQL, (file_id, filename, description, uploader, path))
        conn.commit()


def get_all_files():
    with _db_connection() as conn:
        c = conn.cursor()
        c.execute(SELECT_ALL_FILES_SQL)
        files = c.fetchall()
    return files


def get_file(file_id: str):
    with _db_connection() as conn:
        c = conn.cursor()
        c.execute(SELECT_FILE_BY_ID_SQL, (file_id,))
        file = c.fetchone()
    return file


# --------------------------------------------------------------------------- #
# Filesystem helpers
# --------------------------------------------------------------------------- #
def _ensure_directory(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def _build_upload_path(file_id: str, filename: str) -> str:
    return f'{UPLOAD_DIR}/{file_id}_{filename}'


def _write_bytes(path: str, content: bytes) -> None:
    with open(path, 'wb') as buffer:
        buffer.write(content)


def _write_template(name: str, html: str) -> None:
    with open(f'{TEMPLATES_DIR}/{name}', 'w') as f:
        f.write(html)


def write_default_templates() -> None:
    """Create the templates directory and write the default HTML templates."""
    _ensure_directory(TEMPLATES_DIR)
    _write_template(INDEX_TEMPLATE_NAME, INDEX_TEMPLATE_HTML)
    _write_template(FILE_TEMPLATE_NAME, FILE_TEMPLATE_HTML)


def _file_row_to_context(request: Request, file) -> dict:
    return {
        'request': request,
        'file_id': file[0],
        'filename': file[1],
        'description': file[2],
        'uploader': file[3],
        'file_path': file[4],
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return templates.TemplateResponse(INDEX_TEMPLATE_NAME, {'request': request, 'files': files})


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str=Form(...), uploader: str=Form(...)):
    _ensure_directory(UPLOAD_DIR)
    file_id = str(uuid.uuid4())
    file_path = _build_upload_path(file_id, file.filename)
    _write_bytes(file_path, await file.read())
    save_file_info(file_id, file.filename, description, uploader, file_path)
    return {'message': 'File uploaded successfully', 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail='File not found')
    return templates.TemplateResponse(FILE_TEMPLATE_NAME, _file_row_to_context(request, file))


write_default_templates()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
