"""Employee directory API backed by SQLite.

This module exposes a small FastAPI application for managing departments
and employees. The public interface (module-level names, route handlers,
function signatures and the command-line entry point) is unchanged; the
implementation has been reorganised into configuration, named constants
and small helper functions to make it easier to maintain and extend.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Iterable, List, Tuple

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the application."""

    database_path: str = 'employees.db'
    host: str = '0.0.0.0'
    port: int = 8000


CONFIG = AppConfig()


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_DEPARTMENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
)
"""

CREATE_EMPLOYEES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department_id INTEGER,
    salary REAL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
)
"""

SCHEMA_STATEMENTS = (
    CREATE_DEPARTMENTS_TABLE_SQL,
    CREATE_EMPLOYEES_TABLE_SQL,
)

INSERT_DEPARTMENT_SQL = 'INSERT INTO departments (name) VALUES (?)'
INSERT_EMPLOYEE_SQL = (
    'INSERT INTO employees (name, email, department_id, salary) '
    'VALUES (?, ?, ?, ?)'
)
SELECT_EMPLOYEE_BY_ID_SQL = 'SELECT * FROM employees WHERE id = ?'
DELETE_EMPLOYEE_BY_ID_SQL = 'DELETE FROM employees WHERE id = ?'


# ---------------------------------------------------------------------------
# Response messages
# ---------------------------------------------------------------------------

DEPARTMENT_CREATED_MESSAGE = 'Department created successfully'
EMPLOYEE_CREATED_MESSAGE = 'Employee created successfully'
EMPLOYEE_DELETED_MESSAGE = 'Employee deleted successfully'
EMPLOYEE_NOT_FOUND_DETAIL = 'Employee not found'
SEARCH_QUERY_REQUIRED_DETAIL = 'Search query parameter is required'


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _execute_and_commit(
    db: sqlite3.Connection,
    sql: str,
    params: Tuple[Any, ...],
) -> sqlite3.Cursor:
    """Execute a write statement, commit it and return the cursor."""
    cursor = db.cursor()
    cursor.execute(sql, params)
    db.commit()
    return cursor


def _build_search_sql(search_query: str) -> str:
    """Build the employee search SQL.

    The interpolation is intentionally identical to the original
    implementation so that its behaviour is preserved exactly.
    """
    return (
        f"SELECT * FROM employees WHERE name LIKE '%{search_query}%'"
        f" OR email LIKE '%{search_query}%'"
    )


def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[dict]:
    """Convert SQLite rows into a list of plain dictionaries."""
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def get_db():
    """Create a new SQLite connection using the configured database path."""
    conn = sqlite3.connect(CONFIG.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the database schema if it does not already exist."""
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        conn.commit()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    name: str
    email: str
    department_id: int
    salary: float


class DepartmentCreate(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@app.post('/departments/')
def create_department(department: DepartmentCreate, db: sqlite3.Connection=Depends(get_db)):
    _execute_and_commit(db, INSERT_DEPARTMENT_SQL, (department.name,))
    return {'message': DEPARTMENT_CREATED_MESSAGE}


@app.post('/employees/')
def create_employee(employee: EmployeeCreate, db: sqlite3.Connection=Depends(get_db)):
    params = (
        employee.name,
        employee.email,
        employee.department_id,
        employee.salary,
    )
    _execute_and_commit(db, INSERT_EMPLOYEE_SQL, params)
    return {'message': EMPLOYEE_CREATED_MESSAGE}


@app.get('/employees/search/')
def search_employees(request: Request, db: sqlite3.Connection=Depends(get_db)):
    search_query = request.query_params.get('query', '')
    if not search_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SEARCH_QUERY_REQUIRED_DETAIL,
        )
    cursor = db.cursor()
    cursor.execute(_build_search_sql(search_query))
    return JSONResponse(content=_rows_to_dicts(cursor.fetchall()))


@app.get('/employees/{employee_id}')
def get_employee(employee_id: int, db: sqlite3.Connection=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(SELECT_EMPLOYEE_BY_ID_SQL, (employee_id,))
    employee = cursor.fetchone()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=EMPLOYEE_NOT_FOUND_DETAIL,
        )
    return dict(employee)


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int, db: sqlite3.Connection=Depends(get_db)):
    cursor = _execute_and_commit(db, DELETE_EMPLOYEE_BY_ID_SQL, (employee_id,))
    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=EMPLOYEE_NOT_FOUND_DETAIL,
        )
    return {'message': EMPLOYEE_DELETED_MESSAGE}


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Initialise the database and start the HTTP server."""
    init_db()
    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port)


if __name__ == '__main__':
    main()
