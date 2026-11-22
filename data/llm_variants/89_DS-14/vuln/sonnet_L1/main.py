import sqlite3
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

DATABASE_PATH = 'user_profiles.db'

CREATE_USERS_TABLE_SQL = (
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

app = FastAPI()
templates = Jinja2Templates(directory='templates')


def init_db():
    """Create the users table and seed it with test data if it is empty."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE_SQL)
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)', TEST_USERS)
        conn.commit()
    conn.close()


def get_db_connection():
    """Open a connection whose rows are accessible by column name."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_search_query(username: Optional[str], email: Optional[str]) -> str:
    """Build the user search query from the optional filters.

    NOTE: Values are interpolated directly into the SQL string, preserved
    unchanged from the original implementation.
    """
    query = 'SELECT * FROM users WHERE 1=1'
    if username:
        query += f" AND username LIKE '%{username}%'"
    if email:
        query += f" AND email LIKE '%{email}%'"
    return query


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
    conn = get_db_connection()
    query = build_search_query(username, email)
    try:
        users = conn.execute(query).fetchall()
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail='Database error')
    finally:
        conn.close()
    return templates.TemplateResponse(
        'search_results.html',
        {'request': request, 'users': users, 'query': query},
    )


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str = 'id', order: str = 'ASC'):
    # NOTE: sort_by and order are interpolated directly into the SQL string,
    # preserved unchanged from the original implementation.
    query = f'SELECT id, username, email FROM users ORDER BY {sort_by} {order}'
    conn = get_db_connection()
    try:
        users = conn.execute(query).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse('admin.html', {'request': request, 'users': users})


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
