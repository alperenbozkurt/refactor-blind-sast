"""User profiles web application.

A small FastAPI service backed by SQLite providing a home page, a user
search page and an admin user listing with sortable columns.

The module is organised into configuration, named constants, database
helpers, query-building helpers and HTTP route handlers so that each
piece can be tested and reused independently.
"""

import re
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the application."""

    database_path: str = 'user_profiles.db'
    templates_directory: str = 'templates'
    host: str = '0.0.0.0'
    port: int = 8000


SETTINGS = Settings()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Whitelists used to validate user-supplied sorting options.
ALLOWED_SORT_COLUMNS = ['id', 'username', 'email']
ALLOWED_ORDERS = ['ASC', 'DESC']

DEFAULT_SORT_COLUMN = 'id'
DEFAULT_SORT_ORDER = 'ASC'

# Template names.
HOME_TEMPLATE = 'home.html'
SEARCH_RESULTS_TEMPLATE = 'search_results.html'
ADMIN_TEMPLATE = 'admin.html'

# Database error handling.
DATABASE_ERROR_STATUS_CODE = 500
DATABASE_ERROR_DETAIL = 'Database error'

# SQL statements.
CREATE_USERS_TABLE_SQL = 'CREATE TABLE IF NOT EXISTS users\n                 (id INTEGER PRIMARY KEY, \n                 username TEXT UNIQUE, \n                 email TEXT, \n                 full_name TEXT, \n                 credit_card TEXT)'
COUNT_USERS_SQL = 'SELECT COUNT(*) FROM users'
INSERT_USER_SQL = 'INSERT INTO users VALUES (?, ?, ?, ?, ?)'
SEARCH_USERS_BASE_SQL = 'SELECT id, username, email FROM users WHERE 1=1'
LIST_USERS_BASE_SQL = 'SELECT id, username, email FROM users'
USERNAME_FILTER_SQL = ' AND username LIKE ?'
EMAIL_FILTER_SQL = ' AND email LIKE ?'

# Seed data inserted when the database is first created.
SEED_USERS = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

# Characters stripped from free-text search input.
UNSAFE_SEARCH_CHARS = re.compile(r'[;\'"\\]')


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
templates = Jinja2Templates(directory=SETTINGS.templates_directory)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _create_users_table(cursor: sqlite3.Cursor) -> None:
    """Create the users table if it does not already exist."""
    cursor.execute(CREATE_USERS_TABLE_SQL)


def _users_table_is_empty(cursor: sqlite3.Cursor) -> bool:
    """Return True when the users table contains no rows."""
    cursor.execute(COUNT_USERS_SQL)
    return cursor.fetchone()[0] == 0


def _insert_seed_users(cursor: sqlite3.Cursor) -> None:
    """Insert the default set of test users."""
    cursor.executemany(INSERT_USER_SQL, SEED_USERS)


def init_db():
    """Create the users table and seed it with test data if it is empty."""
    conn = sqlite3.connect(SETTINGS.database_path)
    cursor = conn.cursor()
    _create_users_table(cursor)
    if _users_table_is_empty(cursor):
        _insert_seed_users(cursor)
        conn.commit()
    conn.close()


def get_db_connection():
    """Return a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(SETTINGS.database_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Input sanitisation
# ---------------------------------------------------------------------------

def sanitize_search_input(input_str: Optional[str]) -> Optional[str]:
    """Strip characters that could break or alter SQL from search input."""
    if not input_str:
        return None
    return UNSAFE_SEARCH_CHARS.sub('', input_str)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _build_search_query(username: Optional[str], email: Optional[str]) -> Tuple[str, List[str]]:
    """Build the parameterised user search query and its parameters."""
    query = SEARCH_USERS_BASE_SQL
    params: List[str] = []
    if username:
        query += USERNAME_FILTER_SQL
        params.append(f'%{username}%')
    if email:
        query += EMAIL_FILTER_SQL
        params.append(f'%{email}%')
    return query, params


def _resolve_sorting(sort_by: str, order: str) -> Tuple[str, str]:
    """Fall back to safe defaults for non-whitelisted sorting options."""
    if sort_by not in ALLOWED_SORT_COLUMNS:
        sort_by = DEFAULT_SORT_COLUMN
    if order not in ALLOWED_ORDERS:
        order = DEFAULT_SORT_ORDER
    return sort_by, order


def _build_list_users_query(sort_by: str, order: str) -> str:
    """Build the admin user listing query for validated sorting options."""
    return f'{LIST_USERS_BASE_SQL} ORDER BY {sort_by} {order}'


def _fetch_users(query: str, params: Sequence[str] = ()) -> List[sqlite3.Row]:
    """Execute *query* and return all rows, converting DB errors to HTTP 500."""
    conn = get_db_connection()
    try:
        return conn.execute(query, params).fetchall()
    except sqlite3.Error:
        raise HTTPException(status_code=DATABASE_ERROR_STATUS_CODE, detail=DATABASE_ERROR_DETAIL)
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
    return templates.TemplateResponse(HOME_TEMPLATE, {'request': request})


@app.post('/search', response_class=HTMLResponse)
async def search_users(request: Request, username: Optional[str] = Form(None), email: Optional[str] = Form(None)):
    username = sanitize_search_input(username)
    email = sanitize_search_input(email)
    query, params = _build_search_query(username, email)
    users = _fetch_users(query, params)
    return templates.TemplateResponse(SEARCH_RESULTS_TEMPLATE, {'request': request, 'users': users})


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str = 'id', order: str = 'ASC'):
    sort_by, order = _resolve_sorting(sort_by, order)
    users = _fetch_users(_build_list_users_query(sort_by, order))
    return templates.TemplateResponse(ADMIN_TEMPLATE, {'request': request, 'users': users})


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the development server."""
    uvicorn.run(app, host=SETTINGS.host, port=SETTINGS.port)


if __name__ == '__main__':
    main()
