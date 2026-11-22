"""Employee and department management API.

This module exposes a small FastAPI application backed by a SQLite
database. It is organised into clearly separated sections so it can grow
cleanly within a larger codebase:

* configuration objects and named constants
* SQL statements
* database connection / schema helpers
* request models
* validation and sanitisation helpers
* query helpers
* route handlers
"""

import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the application."""

    database_path: str = "employees.db"
    server_host: str = "0.0.0.0"
    server_port: int = 8000


SETTINGS = Settings()


# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
SEARCH_TERM_DISALLOWED_CHARS = re.compile(r"[;'\"\\]")
MINIMUM_SALARY = 0

MSG_INVALID_EMAIL = "Invalid email format"
MSG_INVALID_SALARY = "Salary must be positive"
MSG_DEPARTMENT_NAME_EMPTY = "Department name cannot be empty"
MSG_DEPARTMENT_ALREADY_EXISTS = "Department already exists"
MSG_DEPARTMENT_CREATE_FAILED = "Failed to create department"
MSG_DEPARTMENT_CREATED = "Department created successfully"
MSG_DEPARTMENT_NOT_FOUND = "Department does not exist"
MSG_EMAIL_ALREADY_EXISTS = "Email already exists"
MSG_EMPLOYEE_CREATE_FAILED = "Failed to create employee"
MSG_EMPLOYEE_CREATED = "Employee created successfully"
MSG_EMPLOYEE_DELETED = "Employee deleted successfully"
MSG_EMPLOYEE_NOT_FOUND = "Employee not found"
MSG_SEARCH_QUERY_REQUIRED = "Search query parameter is required"


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

SQL_CREATE_DEPARTMENTS_TABLE = """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """

SQL_CREATE_EMPLOYEES_TABLE = """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department_id INTEGER,
            salary REAL,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """

SQL_INSERT_DEPARTMENT = "INSERT INTO departments (name) VALUES (?)"
SQL_SELECT_DEPARTMENT_EXISTS = "SELECT 1 FROM departments WHERE id = ?"
SQL_INSERT_EMPLOYEE = (
    "INSERT INTO employees (name, email, department_id, salary) "
    "VALUES (?, ?, ?, ?)"
)
SQL_SEARCH_EMPLOYEES = """
        SELECT * FROM employees 
        WHERE name LIKE ? OR email LIKE ?
    """
SQL_SELECT_EMPLOYEE_BY_ID = "SELECT * FROM employees WHERE id = ?"
SQL_DELETE_EMPLOYEE_BY_ID = "DELETE FROM employees WHERE id = ?"


app = FastAPI()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Create a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(SETTINGS.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_tables(cursor: sqlite3.Cursor) -> None:
    """Create the database schema if it does not already exist."""
    cursor.execute(SQL_CREATE_DEPARTMENTS_TABLE)
    cursor.execute(SQL_CREATE_EMPLOYEES_TABLE)


def init_db():
    """Initialise the database schema."""
    conn = get_db()
    cursor = conn.cursor()
    _create_tables(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    name: str
    email: str
    department_id: int
    salary: float


class DepartmentCreate(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Validation and sanitisation helpers
# ---------------------------------------------------------------------------

def validate_email(email: str) -> str:
    if not EMAIL_PATTERN.match(email):
        raise ValueError(MSG_INVALID_EMAIL)
    return email


def validate_salary(salary: float) -> float:
    if salary <= MINIMUM_SALARY:
        raise ValueError(MSG_INVALID_SALARY)
    return salary


def sanitize_search_term(term: str) -> str:
    if not term:
        return ""
    return SEARCH_TERM_DISALLOWED_CHARS.sub("", term)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _department_exists(cursor: sqlite3.Cursor, department_id: int) -> bool:
    """Return True when a department with the given id exists."""
    cursor.execute(SQL_SELECT_DEPARTMENT_EXISTS, (department_id,))
    return cursor.fetchone() is not None


def _fetch_employee_by_id(
    cursor: sqlite3.Cursor, employee_id: int
) -> Optional[sqlite3.Row]:
    """Return the employee row for the given id, or None when missing."""
    cursor.execute(SQL_SELECT_EMPLOYEE_BY_ID, (employee_id,))
    return cursor.fetchone()


def _build_like_pattern(search_query: str) -> str:
    """Wrap a search term in SQL LIKE wildcards."""
    return f"%{search_query}%"


def _find_employees(
    cursor: sqlite3.Cursor, search_query: str
) -> List[Dict[str, Any]]:
    """Return employees whose name or email matches the search query."""
    like_pattern = _build_like_pattern(search_query)
    cursor.execute(SQL_SEARCH_EMPLOYEES, (like_pattern, like_pattern))
    return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@app.post("/departments/")
def create_department(
    department: DepartmentCreate, db: sqlite3.Connection = Depends(get_db)
):
    if not department.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_DEPARTMENT_NAME_EMPTY,
        )
    cursor = db.cursor()
    try:
        cursor.execute(SQL_INSERT_DEPARTMENT, (department.name,))
        db.commit()
        return {"message": MSG_DEPARTMENT_CREATED}
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_DEPARTMENT_ALREADY_EXISTS,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_DEPARTMENT_CREATE_FAILED,
        )


@app.post("/employees/")
def create_employee(
    employee: EmployeeCreate, db: sqlite3.Connection = Depends(get_db)
):
    try:
        validate_email(employee.email)
        validate_salary(employee.salary)
        cursor = db.cursor()
        if not _department_exists(cursor, employee.department_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=MSG_DEPARTMENT_NOT_FOUND,
            )
        cursor.execute(
            SQL_INSERT_EMPLOYEE,
            (employee.name, employee.email, employee.department_id,
             employee.salary),
        )
        db.commit()
        return {"message": MSG_EMPLOYEE_CREATED}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_EMAIL_ALREADY_EXISTS,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_EMPLOYEE_CREATE_FAILED,
        )


@app.get("/employees/search/")
def search_employees(
    request: Request, db: sqlite3.Connection = Depends(get_db)
):
    search_query = sanitize_search_term(request.query_params.get("query", ""))
    if not search_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_SEARCH_QUERY_REQUIRED,
        )
    cursor = db.cursor()
    return JSONResponse(content=_find_employees(cursor, search_query))


@app.get("/employees/{employee_id}")
def get_employee(employee_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    employee = _fetch_employee_by_id(cursor, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EMPLOYEE_NOT_FOUND,
        )
    return dict(employee)


@app.delete("/employees/{employee_id}")
def delete_employee(
    employee_id: int, db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute(SQL_DELETE_EMPLOYEE_BY_ID, (employee_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EMPLOYEE_NOT_FOUND,
        )
    return {"message": MSG_EMPLOYEE_DELETED}


if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host=SETTINGS.server_host, port=SETTINGS.server_port)
