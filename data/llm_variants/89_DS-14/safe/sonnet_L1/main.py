import re
import sqlite3
from typing import List, Optional, Sequence

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory='templates')

DATABASE_PATH = 'user_profiles.db'

ALLOWED_SORT_COLUMNS = ['id', 'username', 'email']
ALLOWED_ORDERS = ['ASC', 'DESC']
DEFAULT_SORT_COLUMN = 'id'
DEFAULT_ORDER = 'ASC'

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    email TEXT,
    full_name TEXT,
    credit_card TEXT
)
"""

TEST_USERS = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

# Characters removed from search input: ; ' " \
_FORBIDDEN_SEARCH_CHARS = re.compile(r'''[;'"\\]''')


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
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sanitize_search_input(input_str: Optional[str]) -> Optional[str]:
    if not input_str:
        return None
    return _FORBIDDEN_SEARCH_CHARS.sub('', input_str)


def _fetch_users(query: str, params: Sequence = ()) -> list:
    """Run a query and return all rows, translating DB errors into HTTP 500."""
    conn = get_db_connection()
    try:
        return conn.execute(query, params).fetchall()
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail='Database error')
    finally:
        conn.close()


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
    username = sanitize_search_input(username)
    email = sanitize_search_input(email)

    query = 'SELECT id, username, email FROM users WHERE 1=1'
    params: List[str] = []
    if username:
        query += ' AND username LIKE ?'
        params.append(f'%{username}%')
    if email:
        query += ' AND email LIKE ?'
        params.append(f'%{email}%')

    users = _fetch_users(query, params)
    return templates.TemplateResponse(
        'search_results.html', {'request': request, 'users': users}
    )


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str = 'id', order: str = 'ASC'):
    if sort_by not in ALLOWED_SORT_COLUMNS:
        sort_by = DEFAULT_SORT_COLUMN
    if order not in ALLOWED_ORDERS:
        order = DEFAULT_ORDER

    # sort_by and order are validated against whitelists above.
    query = f'SELECT id, username, email FROM users ORDER BY {sort_by} {order}'
    users = _fetch_users(query)
    return templates.TemplateResponse(
        'admin.html', {'request': request, 'users': users}
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
