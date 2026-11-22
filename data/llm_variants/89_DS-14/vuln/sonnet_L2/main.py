from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import uvicorn
from typing import Any, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
DATABASE_PATH = 'user_profiles.db'
TEMPLATES_DIRECTORY = 'templates'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

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

SEED_USERS = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

SEARCH_BASE_QUERY = 'SELECT * FROM users WHERE 1=1'
ADMIN_QUERY_TEMPLATE = 'SELECT id, username, email FROM users ORDER BY {sort_by} {order}'

# Sorting options accepted by the admin view (sensitive columns are excluded).
ALLOWED_SORT_COLUMNS = frozenset({'id', 'username', 'email', 'full_name'})
ALLOWED_SORT_ORDERS = frozenset({'ASC', 'DESC'})

TEMPLATE_HOME = 'home.html'
TEMPLATE_SEARCH_RESULTS = 'search_results.html'
TEMPLATE_ADMIN = 'admin.html'

DB_ERROR_STATUS = 500
DB_ERROR_DETAIL = 'Database error'
BAD_REQUEST_STATUS = 400

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
def _seed_users_if_empty(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(COUNT_USERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_USER_SQL, SEED_USERS)
        conn.commit()


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.cursor().execute(CREATE_USERS_TABLE_SQL)
        _seed_users_if_empty(conn)
    finally:
        conn.close()


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- #
# Query builders
# --------------------------------------------------------------------------- #
def _like_pattern(value: str) -> str:
    return f'%{value}%'


def _build_search_query(
    username: Optional[str], email: Optional[str]
) -> Tuple[str, str, List[str]]:
    """Return (executable_sql, display_sql, params).

    Values are always bound as parameters, never interpolated into the
    executed SQL. The display string mirrors the human-readable query shown
    in the results page.
    """
    sql = SEARCH_BASE_QUERY
    display = SEARCH_BASE_QUERY
    params: List[str] = []
    if username:
        sql += ' AND username LIKE ?'
        display += f" AND username LIKE '%{username}%'"
        params.append(_like_pattern(username))
    if email:
        sql += ' AND email LIKE ?'
        display += f" AND email LIKE '%{email}%'"
        params.append(_like_pattern(email))
    return sql, display, params


def _build_admin_query(sort_by: str, order: str) -> str:
    normalized_order = order.upper()
    if sort_by not in ALLOWED_SORT_COLUMNS or normalized_order not in ALLOWED_SORT_ORDERS:
        raise HTTPException(status_code=BAD_REQUEST_STATUS, detail='Invalid sort parameters')
    return ADMIN_QUERY_TEMPLATE.format(sort_by=sort_by, order=normalized_order)


def _fetch_all(query: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
    conn = get_db_connection()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.on_event('startup')
async def startup():
    init_db()


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(TEMPLATE_HOME, {'request': request})


@app.post('/search', response_class=HTMLResponse)
async def search_users(request: Request, username: Optional[str]=Form(None), email: Optional[str]=Form(None)):
    sql, display_query, params = _build_search_query(username, email)
    try:
        users = _fetch_all(sql, params)
    except sqlite3.Error:
        raise HTTPException(status_code=DB_ERROR_STATUS, detail=DB_ERROR_DETAIL)
    return templates.TemplateResponse(
        TEMPLATE_SEARCH_RESULTS,
        {'request': request, 'users': users, 'query': display_query},
    )


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str='id', order: str='ASC'):
    query = _build_admin_query(sort_by, order)
    users = _fetch_all(query)
    return templates.TemplateResponse(TEMPLATE_ADMIN, {'request': request, 'users': users})


if __name__ == '__main__':
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
