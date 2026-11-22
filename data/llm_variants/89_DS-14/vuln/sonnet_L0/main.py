from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import uvicorn
from typing import Optional

app = FastAPI()
templates = Jinja2Templates(directory='templates')

DB_PATH = 'user_profiles.db'

CREATE_USERS_TABLE = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                 username TEXT UNIQUE, \n'
    '                 email TEXT, \n'
    '                 full_name TEXT, \n'
    '                 credit_card TEXT)'
)

TEST_USERS = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

SORTABLE_COLUMNS = {'id', 'username', 'email', 'full_name', 'credit_card'}
SORT_ORDERS = {'ASC', 'DESC'}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(CREATE_USERS_TABLE)
        c.execute('SELECT COUNT(*) FROM users')
        if c.fetchone()[0] == 0:
            c.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)', TEST_USERS)
            conn.commit()
    finally:
        conn.close()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _build_search_query(username: Optional[str], email: Optional[str]):
    """Return (display_query, sql, params) for the user search.

    The SQL executed uses bound parameters; the display query keeps the
    original textual form that is passed to the template.
    """
    display_query = 'SELECT * FROM users WHERE 1=1'
    sql = 'SELECT * FROM users WHERE 1=1'
    params = []
    if username:
        display_query += f" AND username LIKE '%{username}%'"
        sql += ' AND username LIKE ?'
        params.append(f'%{username}%')
    if email:
        display_query += f" AND email LIKE '%{email}%'"
        sql += ' AND email LIKE ?'
        params.append(f'%{email}%')
    return display_query, sql, params


@app.on_event('startup')
async def startup():
    init_db()


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse('home.html', {'request': request})


@app.post('/search', response_class=HTMLResponse)
async def search_users(
    request: Request,
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
):
    display_query, sql, params = _build_search_query(username, email)
    conn = get_db_connection()
    try:
        users = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail='Database error')
    finally:
        conn.close()
    return templates.TemplateResponse(
        'search_results.html',
        {'request': request, 'users': users, 'query': display_query},
    )


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str = 'id', order: str = 'ASC'):
    if sort_by.lower() not in SORTABLE_COLUMNS or order.upper() not in SORT_ORDERS:
        raise HTTPException(status_code=500, detail='Database error')
    query = f'SELECT id, username, email FROM users ORDER BY {sort_by} {order}'
    conn = get_db_connection()
    try:
        users = conn.execute(query).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse('admin.html', {'request': request, 'users': users})


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
