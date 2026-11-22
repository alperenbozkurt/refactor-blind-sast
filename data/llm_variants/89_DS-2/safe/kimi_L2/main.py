"""Employee management API.

FastAPI service exposing CRUD-style endpoints over an SQLite ``employees``
table.  This is a refactored version of the original single-file module:
behaviour (routes, signatures, status codes, payload shapes and the CLI) is
unchanged, but configuration, SQL statements and shared logic have been
extracted into named constants, a settings object and small helper functions.
"""

import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional  # noqa: F401  (Optional kept for namespace compatibility)

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware  # noqa: F401  (kept for namespace compatibility)
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the service."""

    database_path: str = 'employees.db'
    admin_username: str = 'admin'
    admin_password: str = 'secret'
    allowed_hosts: tuple = ('example.com',)
    server_host: str = '0.0.0.0'
    server_port: int = 8000


settings = Settings()

EMPLOYEE_COLUMNS = ['id', 'name', 'position', 'department', 'salary']
MAX_FIELD_LENGTH = 100
MAX_FILTER_VALUE_LENGTH = 100

RATE_LIMIT_LIST = '100/minute'
RATE_LIMIT_FILTER = '60/minute'
RATE_LIMIT_WRITE = '30/minute'

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        position TEXT,
        department TEXT,
        salary REAL
    )
"""
SEED_EMPLOYEES_SQL = """
    INSERT OR IGNORE INTO employees (id, name, position, department, salary)
    VALUES (?, ?, ?, ?, ?)
"""
SELECT_ALL_EMPLOYEES_SQL = 'SELECT * FROM employees'
FILTER_EMPLOYEES_SQL_TEMPLATE = 'SELECT * FROM employees WHERE {filter_type} = ?'
INSERT_EMPLOYEE_SQL = """
    INSERT INTO employees (id, name, position, department, salary)
    VALUES (?, ?, ?, ?, ?)
"""
DELETE_EMPLOYEE_SQL = 'DELETE FROM employees WHERE id = ?'

SEED_EMPLOYEES = [
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
]


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
security = HTTPBasic()


class Employee(BaseModel):
    id: int
    name: str
    position: str
    department: str
    salary: float


ALLOWED_FILTER_TYPES = {'name', 'position', 'department'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    """Yield an open SQLite connection, always closing it afterwards."""
    conn = sqlite3.connect(settings.database_path)
    try:
        yield conn
    finally:
        conn.close()


def verify_credentials(credentials: HTTPBasicCredentials) -> None:
    """Raise 401 unless the supplied HTTP Basic credentials are valid."""
    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail='Incorrect credentials',
            headers={'WWW-Authenticate': 'Basic'},
        )


def validate_employee_payload(employee: Employee) -> None:
    """Enforce the API-level validation rules for new employees."""
    if employee.salary < 0:
        raise HTTPException(status_code=400, detail='Salary cannot be negative')
    if (len(employee.name) > MAX_FIELD_LENGTH
            or len(employee.position) > MAX_FIELD_LENGTH
            or len(employee.department) > MAX_FIELD_LENGTH):
        raise HTTPException(status_code=400, detail='Field values too long')


def sanitize_filter_value(filter_value: str) -> str:
    # The value is only ever used as a bound parameter; the quote-doubling
    # and truncation mirror the original behaviour exactly.
    return filter_value.replace("'", "''")[:MAX_FILTER_VALUE_LENGTH]


def employee_row_to_dict(row: tuple) -> dict:
    """Map an ``employees`` table row to the API representation."""
    return dict(zip(EMPLOYEE_COLUMNS, row))


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------

def init_db():
    with db_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


@app.on_event('startup')
def startup():
    init_db()
    with db_connection() as conn:
        conn.cursor().executemany(SEED_EMPLOYEES_SQL, SEED_EMPLOYEES)
        conn.commit()


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={'detail': 'Too many requests'},
        headers={'Retry-After': str(exc.retry_after)},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
# NOTE: route functions intentionally have no docstrings or return-type
# annotations, because FastAPI would surface them in the generated OpenAPI
# schema / response model, changing the original module's observable output.

@app.get('/employees/')
@limiter.limit(RATE_LIMIT_LIST)
async def get_all_employees(credentials: HTTPBasicCredentials = Depends(security)):
    verify_credentials(credentials)
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_EMPLOYEES_SQL)
        employees = cursor.fetchall()
    return [employee_row_to_dict(emp) for emp in employees]


@app.get('/employees/filter/')
@limiter.limit(RATE_LIMIT_FILTER)
async def get_employee_by_filter(
    filter_type: str = Query(..., description='Filter type (name, position, department)'),
    filter_value: str = Query(..., description='Value to filter by'),
    credentials: HTTPBasicCredentials = Depends(security),
):
    verify_credentials(credentials)
    if filter_type not in ALLOWED_FILTER_TYPES:
        raise HTTPException(status_code=400, detail='Invalid filter type')
    safe_filter_value = sanitize_filter_value(filter_value)
    query = FILTER_EMPLOYEES_SQL_TEMPLATE.format(filter_type=filter_type)
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (safe_filter_value,))
            employees = cursor.fetchall()
        if not employees:
            raise HTTPException(status_code=404, detail='No employees found')
        return [employee_row_to_dict(emp) for emp in employees]
    except sqlite3.Error:
        raise HTTPException(status_code=400, detail='Database error')
    except Exception:
        # NOTE: the HTTPException(404) raised above is also caught by this
        # handler and converted into a 500, exactly as in the original module.
        raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/employees/')
@limiter.limit(RATE_LIMIT_WRITE)
async def add_employee(employee: Employee, credentials: HTTPBasicCredentials = Depends(security)):
    verify_credentials(credentials)
    validate_employee_payload(employee)
    try:
        with db_connection() as conn:
            conn.cursor().execute(
                INSERT_EMPLOYEE_SQL,
                (employee.id, employee.name, employee.position, employee.department, employee.salary),
            )
            conn.commit()
        return {'message': 'Employee added successfully'}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail='Employee ID already exists')
    except Exception:
        raise HTTPException(status_code=500, detail='Internal server error')


@app.delete('/employees/{employee_id}')
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_employee(employee_id: int, credentials: HTTPBasicCredentials = Depends(security)):
    verify_credentials(credentials)
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(DELETE_EMPLOYEE_SQL, (employee_id,))
        conn.commit()
        affected = cursor.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    uvicorn.run(app, host=settings.server_host, port=settings.server_port)


if __name__ == '__main__':
    main()
