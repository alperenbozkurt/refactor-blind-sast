"""Employee directory API backed by a SQLite database.

The module is organised into clearly separated sections:

* runtime configuration (:class:`Settings`),
* named constants (SQL statements, schema metadata, seed data, messages),
* small database/serialisation helper functions,
* the FastAPI application, its schemas and its routes.
"""

import sqlite3
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the employee service."""

    database_path: str = 'employees.db'
    host: str = '0.0.0.0'
    port: int = 8000


settings = Settings()


# ---------------------------------------------------------------------------
# SQL statements, schema metadata, seed data and messages
# ---------------------------------------------------------------------------

EMPLOYEE_COLUMNS = ('id', 'name', 'position', 'department', 'salary')

CREATE_EMPLOYEES_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT,
            department TEXT,
            salary REAL
        )
    """

SELECT_ALL_EMPLOYEES_SQL = 'SELECT * FROM employees'

INSERT_EMPLOYEE_SQL = """
        INSERT INTO employees (id, name, position, department, salary)
        VALUES (?, ?, ?, ?, ?)
    """

INSERT_OR_IGNORE_EMPLOYEE_SQL = """
        INSERT OR IGNORE INTO employees (id, name, position, department, salary)
        VALUES (?, ?, ?, ?, ?)
    """

DELETE_EMPLOYEE_SQL = 'DELETE FROM employees WHERE id = ?'

SEED_EMPLOYEES = (
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
)

EMPLOYEE_ADDED_MESSAGE = 'Employee added successfully'
EMPLOYEE_DELETED_MESSAGE = 'Employee deleted successfully'

HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_NOT_FOUND = 404


# ---------------------------------------------------------------------------
# Application and schemas
# ---------------------------------------------------------------------------

app = FastAPI()


class Employee(BaseModel):
    id: int
    name: str
    position: str
    department: str
    salary: float


# ---------------------------------------------------------------------------
# Database and serialisation helpers
# ---------------------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    """Open a new connection to the employees database."""
    return sqlite3.connect(settings.database_path)


def _rows_to_dicts(rows) -> list:
    """Convert raw employee rows into dictionaries keyed by column name."""
    return [dict(zip(EMPLOYEE_COLUMNS, row)) for row in rows]


def _employee_to_row(employee: Employee) -> tuple:
    """Convert an :class:`Employee` instance into a database row tuple."""
    return (
        employee.id,
        employee.name,
        employee.position,
        employee.department,
        employee.salary,
    )


def _build_filter_query(filter_type: str, filter_value: str) -> str:
    """Build the SQL statement used to filter employees by a column value."""
    return f"SELECT * FROM employees WHERE {filter_type} = '{filter_value}'"


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------


def init_db():
    """Create the employees table if it does not exist yet."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_EMPLOYEES_TABLE_SQL)
    conn.commit()
    conn.close()


@app.on_event('startup')
def startup():
    """Initialise the database and seed it with the default employees."""
    init_db()
    conn = _connect()
    cursor = conn.cursor()
    cursor.executemany(INSERT_OR_IGNORE_EMPLOYEE_SQL, SEED_EMPLOYEES)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get('/employees/')
def get_all_employees():
    """Return every employee stored in the database."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(SELECT_ALL_EMPLOYEES_SQL)
    employees = cursor.fetchall()
    conn.close()
    return _rows_to_dicts(employees)


@app.get('/employees/filter/')
def get_employee_by_filter(
    filter_type: str = Query(..., description='Filter type (name, position, department)'),
    filter_value: str = Query(..., description='Value to filter by'),
):
    """Return the employees whose ``filter_type`` column equals ``filter_value``."""
    conn = _connect()
    cursor = conn.cursor()
    query = _build_filter_query(filter_type, filter_value)
    try:
        cursor.execute(query)
        employees = cursor.fetchall()
        conn.close()
        if not employees:
            raise HTTPException(
                status_code=HTTP_STATUS_NOT_FOUND, detail='No employees found'
            )
        return _rows_to_dicts(employees)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=HTTP_STATUS_BAD_REQUEST, detail=str(e))


@app.post('/employees/')
def add_employee(employee: Employee):
    """Insert a new employee into the database."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(INSERT_EMPLOYEE_SQL, _employee_to_row(employee))
    conn.commit()
    conn.close()
    return {'message': EMPLOYEE_ADDED_MESSAGE}


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int):
    """Delete the employee with the given identifier."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(DELETE_EMPLOYEE_SQL, (employee_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    if affected == 0:
        raise HTTPException(
            status_code=HTTP_STATUS_NOT_FOUND, detail='Employee not found'
        )
    return {'message': EMPLOYEE_DELETED_MESSAGE}


if __name__ == '__main__':
    uvicorn.run(app, host=settings.host, port=settings.port)
