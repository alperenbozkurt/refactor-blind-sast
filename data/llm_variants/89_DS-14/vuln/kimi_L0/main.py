import sqlite3
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

DATABASE_PATH = 'user_profiles.db'

CREATE_USERS_TABLE_QUERY = (
    'CREATE TABLE IF NOT EXISTS users ('
    'id INTEGER PRIMARY KEY, '
    'username TEXT UNIQUE, '
    'email TEXT, '
    'full_name TEXT, '
    'credit_card TEXT)'
)

TEST_USERS = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

INSERT_USER_QUERY = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
COUNT_USERS_QUERY = 'SELECT COUNT(*) FROM users'
SELECT_ALL_USERS_QUERY = 'SELECT * FROM users WHERE 1=1'
SELECT_USER_SUMMARY_QUERY = 'SELECT id, username, email FROM users'

app = FastAPI()
templates = Jinja2Templates(directory='templates')


def init_db() -> None:
    """Create the users table and seed it with test data if it is empty."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE_QUERY)
    cursor.execute(COUNT_USERS_QUERY)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_USER_QUERY, TEST_USERS)
        conn.commit()
    conn.close()


def get_db_connection() -> sqlite3.Connection:
    """Return a database connection that yields rows accessible by name."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    filters = []
    if username:
        filters.append(f"username LIKE '%{username}%'")
    if email:
        filters.append(f"email LIKE '%{email}%'")

    query = SELECT_ALL_USERS_QUERY
    if filters:
        query += ' AND ' + ' AND '.join(filters)

    conn = get_db_connection()
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
    query = f'{SELECT_USER_SUMMARY_QUERY} ORDER BY {sort_by} {order}'

    conn = get_db_connection()
    try:
        users = conn.execute(query).fetchall()
    finally:
        conn.close()

    return templates.TemplateResponse(
        'admin.html',
        {'request': request, 'users': users},
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
