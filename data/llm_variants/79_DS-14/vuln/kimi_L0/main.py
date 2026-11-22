import os
import sqlite3
import uuid
from contextlib import closing
from typing import List

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DB_PATH = 'file_storage.db'
UPLOAD_DIR = 'uploads'
TEMPLATE_DIR = 'templates'

CREATE_TABLE_QUERY = (
    'CREATE TABLE IF NOT EXISTS files\n'
    '                 (id TEXT PRIMARY KEY,\n'
    '                 filename TEXT,\n'
    '                 description TEXT,\n'
    '                 uploader TEXT,\n'
    '                 path TEXT)'
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

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')


def _get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with closing(_get_connection()) as conn:
        conn.execute(CREATE_TABLE_QUERY)
        conn.commit()


init_db()


def save_file_info(file_id: str, filename: str, description: str, uploader: str, path: str):
    with closing(_get_connection()) as conn:
        conn.execute(
            'INSERT INTO files VALUES (?, ?, ?, ?, ?)',
            (file_id, filename, description, uploader, path),
        )
        conn.commit()


def get_all_files():
    with closing(_get_connection()) as conn:
        return conn.execute(
            'SELECT id, filename, description, uploader FROM files'
        ).fetchall()


def get_file(file_id: str):
    with closing(_get_connection()) as conn:
        return conn.execute(
            'SELECT * FROM files WHERE id=?', (file_id,)
        ).fetchone()


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    return templates.TemplateResponse('index.html', {'request': request, 'files': files})


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile, description: str = Form(...), uploader: str = Form(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
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
    file_id, filename, description, uploader, file_path = file
    return templates.TemplateResponse(
        'file.html',
        {
            'request': request,
            'file_id': file_id,
            'filename': filename,
            'description': description,
            'uploader': uploader,
            'file_path': file_path,
        },
    )


def _write_default_templates():
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    for name, content in (('index.html', INDEX_HTML), ('file.html', FILE_HTML)):
        with open(os.path.join(TEMPLATE_DIR, name), 'w') as f:
            f.write(content)


_write_default_templates()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
