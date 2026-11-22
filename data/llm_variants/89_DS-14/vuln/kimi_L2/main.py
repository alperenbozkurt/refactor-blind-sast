"""User profile directory service.

A small FastAPI application for searching and administering stored
user profiles. Refactored for a larger codebase: runtime configuration
lives in a frozen ``Settings`` object, SQL statements and seed data are
module-level constants, and the route handlers delegate to small,
single-purpose helper functions.

Note: query construction intentionally retains the original value
interpolation in order to keep behaviour identical.
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Form, Depends  # noqa: F401  (kept for compatibility)
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


settings = Settings()


# ---------------------------------------------------------------------------
# SQL statements and seed data
# ---------------------------------------------------------------------------

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
SEARCH_USERS_BASE_SQL = 'SELECT * FROM users WHERE 1=1'

TEST_USERS: List[Tuple[int, str, str, str, str]] = [
    (1, 'jdoe', 'jdoe@example.com', 'John Doe', '4111111111111111'),
    (2, 'asmith', 'asmith@example.com', 'Alice Smith', '5555555555554444'),
    (3, 'bjones', 'bjones@example.com', 'Bob Jones', '378282246310005'),
]

# Template names.
HOME_TEMPLATE = 'home.html'
SEARCH_RESULTS_TEMPLATE = 'search_results.html'
ADMIN_TEMPLATE = 'admin.html'

DATABASE_ERROR_DETAIL = 'Database error'


app = FastAPI()
templates = Jinja2Templates(directory=settings.templates_directory)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _table_is_empty(cursor: sqlite3.Cursor) -> bool:
    """Return True when the users table contains no rows."""
    cursor.execute(COUNT_USERS_SQL)
    return cursor.fetchone()[0] == 0


def _seed_test_users(cursor: sqlite3.Cursor) -> None:
    """Insert the default set of test users."""
    cursor.executemany(INSERT_USER_SQL, TEST_USERS)


def init_db():
    conn = sqlite3.connect(settings.database_path)
    cursor = conn.cursor()
    cursor.execute(CREATE_USERS_TABLE_SQL)
    if _table_is_empty(cursor):
        _seed_test_users(cursor)
        conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

def _build_search_query(username: Optional[str], email: Optional[str]) -> str:
    """Build the user search query from the optional filters."""
    query = SEARCH_USERS_BASE_SQL
    if username:
        query += f" AND username LIKE '%{username}%'"
    if email:
        query += f" AND email LIKE '%{email}%'"
    return query


def _build_admin_query(sort_by: str, order: str) -> str:
    """Build the admin listing query with the requested ordering."""
    return f'SELECT id, username, email FROM users ORDER BY {sort_by} {order}'


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
    conn = get_db_connection()
    query = _build_search_query(username, email)
    try:
        users = conn.execute(query).fetchall()
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail=DATABASE_ERROR_DETAIL)
    finally:
        conn.close()
    return templates.TemplateResponse(
        SEARCH_RESULTS_TEMPLATE,
        {'request': request, 'users': users, 'query': query},
    )


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_view(request: Request, sort_by: str = 'id', order: str = 'ASC'):
    conn = get_db_connection()
    users = conn.execute(_build_admin_query(sort_by, order)).fetchall()
    conn.close()
    return templates.TemplateResponse(ADMIN_TEMPLATE, {'request': request, 'users': users})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == '__main__':
    main()
