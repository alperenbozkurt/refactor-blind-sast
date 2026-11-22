"""FastAPI file-storage application.

The behaviour (routes, module-level names, function signatures and CLI) is
identical to the original module, but the implementation is organised into
configuration constants, SQL/template constants and small single-purpose
helper functions so it can grow cleanly as part of a larger codebase.
"""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Iterator, List

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'file_storage.db'
UPLOAD_DIRECTORY = 'uploads'
STATIC_DIRECTORY = 'static'
TEMPLATES_DIRECTORY = 'templates'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

UPLOAD_SUCCESS_MESSAGE = 'File uploaded successfully'
FILE_NOT_FOUND_DETAIL = 'File not found'

INDEX_TEMPLATE_PATH = f'{TEMPLATES_DIRECTORY}/index.html'
FILE_TEMPLATE_PATH = f'{TEMPLATES_DIRECTORY}/file.html'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_FILES_TABLE_SQL = 'CREATE TABLE IF NOT EXISTS files\n                 (id TEXT PRIMARY KEY,\n                 filename TEXT,\n                 description TEXT,\n                 uploader TEXT,\n                 path TEXT)'
INSERT_FILE_SQL = 'INSERT INTO files VALUES (?, ?, ?, ?, ?)'
SELECT_ALL_FILES_SQL = 'SELECT id, filename, description, uploader FROM files'
SELECT_FILE_BY_ID_SQL = 'SELECT * FROM files WHERE id=?'

# ---------------------------------------------------------------------------
# Default HTML templates (written to disk at import time)
# ---------------------------------------------------------------------------

INDEX_HTML_TEMPLATE = """
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

FILE_HTML_TEMPLATE = """
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
        <div>{{ description | safe }}</div>
    </div>
    <a href="/">Back to files</a>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@contextmanager
def _db_connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection to the application database, always closing it."""
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        yield connection
    finally:
        connection.close()


def _ensure_directory(path: str) -> None:
    """Create ``path`` (including parents) if it does not already exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def _write_default_templates() -> None:
    """(Re)generate the bundled Jinja2 templates on disk."""
    _ensure_directory(TEMPLATES_DIRECTORY)
    with open(INDEX_TEMPLATE_PATH, 'w') as f:
        f.write(INDEX_HTML_TEMPLATE)
    with open(FILE_TEMPLATE_PATH, 'w') as f:
        f.write(FILE_HTML_TEMPLATE)


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
app.mount('/static', StaticFiles(directory=STATIC_DIRECTORY), name='static')
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)

# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def init_db():
    with _db_connection() as connection:
        connection.execute(CREATE_FILES_TABLE_SQL)
        connection.commit()


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    with _db_connection() as connection:
        connection.execute(INSERT_FILE_SQL, (file_id, filename, description, uploader, path))
        connection.commit()


def get_all_files():
    with _db_connection() as connection:
        return connection.execute(SELECT_ALL_FILES_SQL).fetchall()


def get_file(file_id: str):
    with _db_connection() as connection:
        return connection.execute(SELECT_FILE_BY_ID_SQL, (file_id,)).fetchone()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return templates.TemplateResponse('index.html', {'request': request, 'files': files})


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str = Form(...), uploader: str = Form(...)):
    _ensure_directory(UPLOAD_DIRECTORY)
    file_id = str(uuid.uuid4())
    file_path = f'{UPLOAD_DIRECTORY}/{file_id}_{file.filename}'
    with open(file_path, 'wb') as buffer:
        buffer.write(await file.read())
    save_file_info(file_id, file.filename, description, uploader, file_path)
    return {'message': UPLOAD_SUCCESS_MESSAGE, 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND_DETAIL)
    record_id, filename, description, uploader, file_path = file
    return templates.TemplateResponse(
        'file.html',
        {
            'request': request,
            'file_id': record_id,
            'filename': filename,
            'description': description,
            'uploader': uploader,
            'file_path': file_path,
        },
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

_write_default_templates()


def main() -> None:
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
