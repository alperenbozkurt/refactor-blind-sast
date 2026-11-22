"""User profile directory web application.

Exposes a public search page and an admin user listing backed by a
SQLite database. The database schema is created and seeded with sample
users when the application starts.
"""

import re
import sqlite3
from typing import List, Optional, Sequence, Tuple

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'user_profiles.db'
TEMPLATES_DIR = 'templates'

ALLOWED_SORT_COLUMNS = ['id', 'username', 'email']
ALLOWED_ORDERS = ['ASC', 'DESC']

DEFAULT_SORT_COLUMN = 'id'
DEFAULT_SORT_ORDER = 'ASC'

DB_ERROR_STATUS_CODE = 500
DB_ERROR_DETAIL = 'Database error'

# Characters removed from user-supplied search terms before the terms are
# used in LIKE patterns.
_SEARCH_INPUT_DISALLOWED_CHARS = re.compile(r'[;\'"\\]')

# ---------------------------------------------------------------------------
# SQL statements and seed data
# ---------------------------------------------------------------------------

_CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY,
         username TEXT UNIQUE,
         email TEXT,
         full_name TEXT,
         credit_card TEXT)
"""

_COUNT_USERS = 'SELECT COUNT(*) FROM users'
_INSERT_USER = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
_SELECT_PUBLIC_USER_FIELDS = 'SELECT id, username, email FROM users'

TEST_USERS = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db():
    """Create the users table if needed and seed it when it is empty."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(_CREATE_USERS_TABLE)
    cursor.execute(_COUNT_USERS)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(_INSERT_USER, TEST_USERS)
        conn.commit()
    conn.close()


def get_db_connection():
    """Open a connection that returns rows as sqlite3.Row objects."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Input handling and query construction
# ---------------------------------------------------------------------------

def sanitize_search_input(input_str: Optional[str]) -> Optional[str]:
    """Return None for empty input, otherwise strip disallowed characters."""
    if not input_str:
        return None
    return _SEARCH_INPUT_DISALLOWED_CHARS.sub('', input_str)


def _build_search_query(
    username: Optional[str], email: Optional[str]
) -> Tuple[str, List[str]]:
    """Build the parameterized search query and its bound parameters."""
    query = _SELECT_PUBLIC_USER_FIELDS + ' WHERE 1=1'
    params = []
    if username:
        query += ' AND username LIKE ?'
        params.append(f'%{username}%')
    if email:
        query += ' AND email LIKE ?'
        params.append(f'%{email}%')
    return query, params


def _build_admin_query(sort_by: str, order: str) -> str:
    """Build the admin listing query with whitelisted sorting options."""
    if sort_by not in ALLOWED_SORT_COLUMNS:
        sort_by = DEFAULT_SORT_COLUMN
    if order not in ALLOWED_ORDERS:
        order = DEFAULT_SORT_ORDER
    # sort_by and order are restricted to the whitelists above, so it is
    # safe to interpolate them into the SQL string.
    return f'{_SELECT_PUBLIC_USER_FIELDS} ORDER BY {sort_by} {order}'


def _render_user_table(
    request: Request,
    template_name: str,
    query: str,
    params: Sequence[str] = (),
):
    """Run a user query and render the results, mapping DB errors to 500."""
    conn = get_db_connection()
    try:
        users = conn.execute(query, params).fetchall()
        return templates.TemplateResponse(
            template_name, {'request': request, 'users': users}
        )
    except sqlite3.Error:
        raise HTTPException(
            status_code=DB_ERROR_STATUS_CODE, detail=DB_ERROR_DETAIL
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

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
    query, params = _build_search_query(username, email)
    return _render_user_table(request, 'search_results.html', query, params)


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str = 'id', order: str = 'ASC'):
    query = _build_admin_query(sort_by, order)
    return _render_user_table(request, 'admin.html', query)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
