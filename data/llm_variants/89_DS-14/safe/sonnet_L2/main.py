from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import uvicorn
from typing import Any, List, Optional, Sequence, Tuple
import re

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
DATABASE_PATH = 'user_profiles.db'
TEMPLATES_DIRECTORY = 'templates'

HOST = '0.0.0.0'
PORT = 8000

ALLOWED_SORT_COLUMNS = ['id', 'username', 'email']
ALLOWED_ORDERS = ['ASC', 'DESC']
DEFAULT_SORT_COLUMN = 'id'
DEFAULT_ORDER = 'ASC'

DB_ERROR_STATUS_CODE = 500
DB_ERROR_DETAIL = 'Database error'

SEARCH_INPUT_FORBIDDEN_PATTERN = '[;\\\'"\\\\]'

CREATE_USERS_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS users\n'
    '                 (id INTEGER PRIMARY KEY, \n'
    '                 username TEXT UNIQUE, \n'
    '                 email TEXT, \n'
    '                 full_name TEXT, \n'
    '                 credit_card TEXT)'
)
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
BASE_SEARCH_QUERY = 'SELECT id, username, email FROM users WHERE 1=1'
USERNAME_FILTER_CLAUSE = ' AND username LIKE ?'
EMAIL_FILTER_CLAUSE = ' AND email LIKE ?'
ADMIN_LIST_QUERY_TEMPLATE = 'SELECT id, username, email FROM users ORDER BY {sort_by} {order}'

SEED_USERS = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

HOME_TEMPLATE = 'home.html'
SEARCH_RESULTS_TEMPLATE = 'search_results.html'
ADMIN_TEMPLATE = 'admin.html'

# ---------------------------------------------------------------------------
# Application objects
# ---------------------------------------------------------------------------
app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _seed_users_if_empty(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(COUNT_USERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_USER_SQL, list(SEED_USERS))
        conn.commit()


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE_SQL)
    _seed_users_if_empty(conn)
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_all(query: str, params: Optional[Sequence[Any]] = None) -> list:
    """Run a read query, converting database errors to HTTP 500 responses."""
    conn = get_db_connection()
    try:
        if params is None:
            return conn.execute(query).fetchall()
        return conn.execute(query, params).fetchall()
    except sqlite3.Error:
        raise HTTPException(status_code=DB_ERROR_STATUS_CODE, detail=DB_ERROR_DETAIL)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Input handling / query building
# ---------------------------------------------------------------------------
def sanitize_search_input(input_str: Optional[str]) -> Optional[str]:
    if not input_str:
        return None
    return re.sub(SEARCH_INPUT_FORBIDDEN_PATTERN, '', input_str)


def _like_pattern(value: str) -> str:
    return f'%{value}%'


def _build_search_query(
    username: Optional[str], email: Optional[str]
) -> Tuple[str, List[str]]:
    query = BASE_SEARCH_QUERY
    params: List[str] = []
    if username:
        query += USERNAME_FILTER_CLAUSE
        params.append(_like_pattern(username))
    if email:
        query += EMAIL_FILTER_CLAUSE
        params.append(_like_pattern(email))
    return query, params


def _normalize_sort_column(sort_by: str) -> str:
    return sort_by if sort_by in ALLOWED_SORT_COLUMNS else DEFAULT_SORT_COLUMN


def _normalize_order(order: str) -> str:
    return order if order in ALLOWED_ORDERS else DEFAULT_ORDER


def _build_admin_query(sort_by: str, order: str) -> str:
    return ADMIN_LIST_QUERY_TEMPLATE.format(
        sort_by=_normalize_sort_column(sort_by),
        order=_normalize_order(order),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.on_event('startup')
async def startup():
    init_db()


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(HOME_TEMPLATE, {'request': request})


@app.post('/search', response_class=HTMLResponse)
async def search_users(request: Request, username: Optional[str]=Form(None), email: Optional[str]=Form(None)):
    username = sanitize_search_input(username)
    email = sanitize_search_input(email)
    query, params = _build_search_query(username, email)
    users = _fetch_all(query, params)
    return templates.TemplateResponse(
        SEARCH_RESULTS_TEMPLATE, {'request': request, 'users': users}
    )


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str='id', order: str='ASC'):
    query = _build_admin_query(sort_by, order)
    users = _fetch_all(query)
    return templates.TemplateResponse(
        ADMIN_TEMPLATE, {'request': request, 'users': users}
    )


if __name__ == '__main__':
    uvicorn.run(app, host=HOST, port=PORT)
