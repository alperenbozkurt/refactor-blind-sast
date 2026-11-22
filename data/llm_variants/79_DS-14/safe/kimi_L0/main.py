import contextlib
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

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_DIR = 'uploads'
DB_PATH = 'file_storage.db'

_CREATE_FILES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    filename TEXT,
    description TEXT,
    uploader TEXT,
    path TEXT
)
"""
_INSERT_FILE_SQL = 'INSERT INTO files VALUES (?, ?, ?, ?, ?)'
_SELECT_ALL_FILES_SQL = 'SELECT id, filename, description, uploader FROM files'
_SELECT_FILE_BY_ID_SQL = 'SELECT * FROM files WHERE id=?'


@contextlib.contextmanager
def _db_cursor():
    """Yield a cursor, committing on success and always closing the connection."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _db_cursor() as cursor:
        cursor.execute(_CREATE_FILES_TABLE_SQL)


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    sanitized_desc = html.escape(description)
    sanitized_uploader = html.escape(uploader)
    with _db_cursor() as cursor:
        cursor.execute(
            _INSERT_FILE_SQL,
            (file_id, filename, sanitized_desc, sanitized_uploader, path),
        )


def get_all_files():
    with _db_cursor() as cursor:
        cursor.execute(_SELECT_ALL_FILES_SQL)
        return cursor.fetchall()


def get_file(file_id: str):
    with _db_cursor() as cursor:
        cursor.execute(_SELECT_FILE_BY_ID_SQL, (file_id,))
        return cursor.fetchone()


def is_allowed_file(filename: str):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename: str):
    filename = Path(filename).name
    return re.sub(r'[^\w.-]', '_', filename)


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return templates.TemplateResponse('index.html', {'request': request, 'files': files})


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str = Form(...), uploader: str = Form(...)):
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
            # NOTE: this 413 is deliberately caught below and re-raised as a
            # 500, preserving the original behaviour.
            raise HTTPException(status_code=413, detail='File too large')
        with open(file_path, 'wb') as buffer:
            buffer.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    save_file_info(file_id, safe_filename, description, uploader, file_path)
    return {'message': 'File uploaded successfully', 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail='File not found')
    stored_id, filename, description, uploader, file_path = file
    return templates.TemplateResponse(
        'file.html',
        {
            'request': request,
            'file_id': stored_id,
            'filename': filename,
            'description': description,
            'uploader': uploader,
            'file_path': file_path,
        },
    )


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


def _write_default_templates():
    os.makedirs('templates', exist_ok=True)
    with open('templates/index.html', 'w') as f:
        f.write(_INDEX_HTML)
    with open('templates/file.html', 'w') as f:
        f.write(_FILE_HTML)


_write_default_templates()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
