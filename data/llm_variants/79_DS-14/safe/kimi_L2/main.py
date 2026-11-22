"""File storage web application built with FastAPI.

Organised for a larger codebase: configuration is centralised in
:class:`Settings`, SQL statements live in named constants, database access
goes through a single context manager, and the default HTML templates are
stored as named constants that are written to disk at import time.

All public module-level names, function signatures, routes and the
command-line interface are unchanged from the original module.
"""

import html
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Central application configuration."""

    database_path: str = 'file_storage.db'
    upload_dir: str = 'uploads'
    static_dir: str = 'static'
    static_route: str = '/static'
    templates_dir: str = 'templates'
    max_file_size: int = 10 * 1024 * 1024  # 10 MiB
    allowed_extensions: set = field(
        default_factory=lambda: {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    )
    host: str = '0.0.0.0'
    port: int = 8000


SETTINGS = Settings()

# Public constants (unchanged from the original module).
MAX_FILE_SIZE = SETTINGS.max_file_size
ALLOWED_EXTENSIONS = SETTINGS.allowed_extensions
UPLOAD_DIR = SETTINGS.upload_dir
DATABASE_PATH = SETTINGS.database_path
TEMPLATES_DIR = SETTINGS.templates_dir

# HTTP status codes.
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_PAYLOAD_TOO_LARGE = 413
HTTP_INTERNAL_SERVER_ERROR = 500

# User-facing messages.
MSG_NO_FILE_UPLOADED = 'No file uploaded'
MSG_FILE_TYPE_NOT_ALLOWED = 'File type not allowed'
MSG_FILE_TOO_LARGE = 'File too large'
MSG_FILE_NOT_FOUND = 'File not found'
MSG_UPLOAD_SUCCESS = 'File uploaded successfully'


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
app.mount(SETTINGS.static_route, StaticFiles(directory=SETTINGS.static_dir), name='static')
templates = Jinja2Templates(directory=SETTINGS.templates_dir)


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------

_SQL_CREATE_FILES_TABLE = (
    'CREATE TABLE IF NOT EXISTS files '
    '(id TEXT PRIMARY KEY, filename TEXT, description TEXT, uploader TEXT, path TEXT)'
)
_SQL_INSERT_FILE = 'INSERT INTO files VALUES (?, ?, ?, ?, ?)'
_SQL_SELECT_ALL_FILES = 'SELECT id, filename, description, uploader FROM files'
_SQL_SELECT_FILE_BY_ID = 'SELECT * FROM files WHERE id=?'


@contextmanager
def _db_connection(db_path: str = DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    """Yield an open SQLite connection, closing it when the block exits."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create the files table if it does not exist yet."""
    with _db_connection() as conn:
        conn.execute(_SQL_CREATE_FILES_TABLE)
        conn.commit()


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    """Escape user-supplied text and persist the file metadata."""
    sanitized_desc = html.escape(description)
    sanitized_uploader = html.escape(uploader)
    with _db_connection() as conn:
        conn.execute(
            _SQL_INSERT_FILE,
            (file_id, filename, sanitized_desc, sanitized_uploader, path),
        )
        conn.commit()


def get_all_files():
    """Return ``(id, filename, description, uploader)`` rows for all files."""
    with _db_connection() as conn:
        return conn.execute(_SQL_SELECT_ALL_FILES).fetchall()


def get_file(file_id: str):
    """Return the full row for ``file_id``, or ``None`` if it is missing."""
    with _db_connection() as conn:
        return conn.execute(_SQL_SELECT_FILE_BY_ID, (file_id,)).fetchone()


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def is_allowed_file(filename: str):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename: str):
    filename = Path(filename).name
    return re.sub(r'[^\w\.-]', '_', filename)


def _build_file_path(file_id: str, safe_filename: str) -> str:
    return os.path.join(UPLOAD_DIR, f'{file_id}_{safe_filename}')


async def _write_upload(file: UploadFile, file_path: str) -> None:
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=HTTP_PAYLOAD_TOO_LARGE, detail=MSG_FILE_TOO_LARGE)
    with open(file_path, 'wb') as buffer:
        buffer.write(contents)


# ---------------------------------------------------------------------------
# Default templates
# ---------------------------------------------------------------------------

_INDEX_HTML = """
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

_FILE_HTML = """
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

_DEFAULT_TEMPLATES = (
    ('index.html', _INDEX_HTML),
    ('file.html', _FILE_HTML),
)


def _write_default_templates(directory: str = TEMPLATES_DIR) -> None:
    """Create ``directory`` if needed and (re)write the bundled templates."""
    if not os.path.exists(directory):
        os.makedirs(directory)
    for name, content in _DEFAULT_TEMPLATES:
        with open(os.path.join(directory, name), 'w') as f:
            f.write(content)


_write_default_templates()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _render(request: Request, template_name: str, **context):
    return templates.TemplateResponse(template_name, {'request': request, **context})


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return _render(request, 'index.html', files=files)


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str = Form(...), uploader: str = Form(...)):
    if not file:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=MSG_NO_FILE_UPLOADED)
    if not is_allowed_file(file.filename):
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=MSG_FILE_TYPE_NOT_ALLOWED)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_filename = sanitize_filename(file.filename)
    file_id = str(uuid.uuid4())
    file_path = _build_file_path(file_id, safe_filename)
    try:
        await _write_upload(file, file_path)
    except Exception as e:
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=str(e))
    save_file_info(file_id, safe_filename, description, uploader, file_path)
    return {'message': MSG_UPLOAD_SUCCESS, 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail=MSG_FILE_NOT_FOUND)
    return _render(
        request,
        'file.html',
        file_id=file[0],
        filename=file[1],
        description=file[2],
        uploader=file[3],
        file_path=file[4],
    )


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host=SETTINGS.host, port=SETTINGS.port)
