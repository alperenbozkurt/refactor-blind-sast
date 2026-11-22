from contextlib import closing
from typing import List

import os
import sqlite3
import uuid

from fastapi import FastAPI, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DB_PATH = 'file_storage.db'
UPLOAD_DIR = 'uploads'
TEMPLATE_DIR = 'templates'

_COLUMN_INDENT = ' ' * 17
CREATE_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS files\n'
    f'{_COLUMN_INDENT}(id TEXT PRIMARY KEY,\n'
    f'{_COLUMN_INDENT}filename TEXT,\n'
    f'{_COLUMN_INDENT}description TEXT,\n'
    f'{_COLUMN_INDENT}uploader TEXT,\n'
    f'{_COLUMN_INDENT}path TEXT)'
)

INDEX_TEMPLATE = """
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

FILE_TEMPLATE = """
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

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory=TEMPLATE_DIR)


# --- Database helpers -------------------------------------------------------

def _connect():
    """Return a connection that is closed automatically when the block exits."""
    return closing(sqlite3.connect(DB_PATH))


def init_db():
    with _connect() as conn:
        conn.cursor().execute(CREATE_TABLE_SQL)
        conn.commit()


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    with _connect() as conn:
        conn.cursor().execute(
            'INSERT INTO files VALUES (?, ?, ?, ?, ?)',
            (file_id, filename, description, uploader, path),
        )
        conn.commit()


def get_all_files():
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, filename, description, uploader FROM files')
        return cursor.fetchall()


def get_file(file_id: str):
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM files WHERE id=?', (file_id,))
        return cursor.fetchone()


# --- Routes -----------------------------------------------------------------

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return templates.TemplateResponse('index.html', {'request': request, 'files': files})


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str=Form(...), uploader: str=Form(...)):
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    file_id = str(uuid.uuid4())
    file_path = f'{UPLOAD_DIR}/{file_id}_{file.filename}'

    with open(file_path, 'wb') as buffer:
        buffer.write(await file.read())

    save_file_info(file_id, file.filename, description, uploader, file_path)
    return {'message': 'File uploaded successfully', 'file_id': file_id}


@app.get('/file/{file_id}', response_class=HTMLResponse)
async def view_file(request: Request, file_id: str):
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail='File not found')

    context = {
        'request': request,
        'file_id': file[0],
        'filename': file[1],
        'description': file[2],
        'uploader': file[3],
        'file_path': file[4],
    }
    return templates.TemplateResponse('file.html', context)


# --- Template files ---------------------------------------------------------

if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR)

with open(f'{TEMPLATE_DIR}/index.html', 'w') as f:
    f.write(INDEX_TEMPLATE)

with open(f'{TEMPLATE_DIR}/file.html', 'w') as f:
    f.write(FILE_TEMPLATE)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
