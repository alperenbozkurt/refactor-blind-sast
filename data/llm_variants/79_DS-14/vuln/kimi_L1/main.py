"""Minimal FastAPI file-storage application.

Uploaded files are written to the ``uploads`` directory and their metadata is
stored in a SQLite database. Basic HTML templates are generated at import
time so the application runs out of the box.
"""

import os
import sqlite3
import uuid
from contextlib import closing
from typing import List

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DATABASE_PATH = 'file_storage.db'
UPLOADS_DIR = 'uploads'
STATIC_DIR = 'static'
TEMPLATES_DIR = 'templates'

CREATE_FILES_TABLE = (
    'CREATE TABLE IF NOT EXISTS files\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 filename TEXT,\n'
    '                 description TEXT,\n'
    '                 uploader TEXT,\n'
    '                 path TEXT)'
)
INSERT_FILE = 'INSERT INTO files VALUES (?, ?, ?, ?, ?)'
SELECT_ALL_FILES = 'SELECT id, filename, description, uploader FROM files'
SELECT_FILE_BY_ID = 'SELECT * FROM files WHERE id=?'

app = FastAPI()
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def init_db():
    """Create the files table if it does not already exist."""
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        conn.execute(CREATE_FILES_TABLE)
        conn.commit()


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    """Store the metadata for an uploaded file."""
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        conn.execute(INSERT_FILE, (file_id, filename, description, uploader, path))
        conn.commit()


def get_all_files():
    """Return (id, filename, description, uploader) for every uploaded file."""
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        return conn.execute(SELECT_ALL_FILES).fetchall()


def get_file(file_id: str):
    """Return the full row for ``file_id``, or ``None`` when it is unknown."""
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        return conn.execute(SELECT_FILE_BY_ID, (file_id,)).fetchone()


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return templates.TemplateResponse(
        'index.html', {'request': request, 'files': files}
    )


@app.post('/upload')
async def upload_file(
    request: Request,
    file: UploadFile,
    description: str = Form(...),
    uploader: str = Form(...),
):
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
    file_id = str(uuid.uuid4())
    file_path = f'{UPLOADS_DIR}/{file_id}_{file.filename}'
    with open(file_path, 'wb') as buffer:
        buffer.write(await file.read())
    save_file_info(file_id, file.filename, description, uploader, file_path)
    return {'message': 'File uploaded successfully', 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail='File not found')
    return templates.TemplateResponse(
        'file.html',
        {
            'request': request,
            'file_id': file[0],
            'filename': file[1],
            'description': file[2],
            'uploader': file[3],
            'file_path': file[4],
        },
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
        <div>{{ description | safe }}</div>
    </div>
    <a href="/">Back to files</a>
</body>
</html>
"""

if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

for template_name, template_content in (
    ('index.html', INDEX_HTML),
    ('file.html', FILE_HTML),
):
    with open(os.path.join(TEMPLATES_DIR, template_name), 'w') as f:
        f.write(template_content)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
