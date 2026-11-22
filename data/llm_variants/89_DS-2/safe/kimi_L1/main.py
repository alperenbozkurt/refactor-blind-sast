"""Employee management API.

A FastAPI application exposing endpoints over a SQLite database of
employees. All endpoints require HTTP Basic authentication and are
rate limited per client IP.
"""

import secrets
import sqlite3
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
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

_DATABASE_PATH = 'employees.db'

_AUTH_USERNAME = 'admin'
_AUTH_PASSWORD = 'secret'

_MAX_TEXT_FIELD_LENGTH = 100
_MAX_FILTER_VALUE_LENGTH = 100

_EMPLOYEE_COLUMNS = ('id', 'name', 'position', 'department', 'salary')

_CREATE_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT,
            department TEXT,
            salary REAL
        )
    '''

_INSERT_EMPLOYEE_SQL = '''
            INSERT INTO employees (id, name, position, department, salary)
            VALUES (?, ?, ?, ?, ?)
        '''

_SEED_EMPLOYEES_SQL = '''
        INSERT OR IGNORE INTO employees (id, name, position, department, salary)
        VALUES (?, ?, ?, ?, ?)
    '''

_SEED_EMPLOYEES = (
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
)

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['example.com'])
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

def _verify_credentials(credentials: HTTPBasicCredentials) -> None:
    """Raise a 401 error unless the supplied Basic credentials are valid."""
    correct_username = secrets.compare_digest(credentials.username, _AUTH_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, _AUTH_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail='Incorrect credentials',
            headers={'WWW-Authenticate': 'Basic'},
        )


def _get_connection() -> sqlite3.Connection:
    """Open a new connection to the employees database."""
    return sqlite3.connect(_DATABASE_PATH)


def _employee_to_dict(row: tuple) -> dict:
    """Map an employee table row onto its column names."""
    return dict(zip(_EMPLOYEE_COLUMNS, row))


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------

def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(_CREATE_TABLE_SQL)
    conn.commit()
    conn.close()


@app.on_event('startup')
def startup():
    init_db()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.executemany(_SEED_EMPLOYEES_SQL, _SEED_EMPLOYEES)
    conn.commit()
    conn.close()


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

@app.get('/employees/')
@limiter.limit('100/minute')
async def get_all_employees(credentials: HTTPBasicCredentials = Depends(security)):
    _verify_credentials(credentials)
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employees')
    employees = cursor.fetchall()
    conn.close()
    return [_employee_to_dict(emp) for emp in employees]


@app.get('/employees/filter/')
@limiter.limit('60/minute')
async def get_employee_by_filter(
    filter_type: str = Query(..., description='Filter type (name, position, department)'),
    filter_value: str = Query(..., description='Value to filter by'),
    credentials: HTTPBasicCredentials = Depends(security),
):
    _verify_credentials(credentials)
    if filter_type not in ALLOWED_FILTER_TYPES:
        raise HTTPException(status_code=400, detail='Invalid filter type')

    safe_filter_value = filter_value.replace("'", "''")[:_MAX_FILTER_VALUE_LENGTH]
    query = f'SELECT * FROM employees WHERE {filter_type} = ?'

    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, (safe_filter_value,))
        employees = cursor.fetchall()
        conn.close()
        if not employees:
            # Raised inside the try block on purpose: the generic exception
            # handler below catches it and returns a 500 response. This
            # preserves the original externally visible behaviour.
            raise HTTPException(status_code=404, detail='No employees found')
        return [_employee_to_dict(emp) for emp in employees]
    except sqlite3.Error:
        conn.close()
        raise HTTPException(status_code=400, detail='Database error')
    except Exception:
        conn.close()
        raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/employees/')
@limiter.limit('30/minute')
async def add_employee(employee: Employee, credentials: HTTPBasicCredentials = Depends(security)):
    _verify_credentials(credentials)
    if employee.salary < 0:
        raise HTTPException(status_code=400, detail='Salary cannot be negative')
    if any(
        len(field) > _MAX_TEXT_FIELD_LENGTH
        for field in (employee.name, employee.position, employee.department)
    ):
        raise HTTPException(status_code=400, detail='Field values too long')

    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            _INSERT_EMPLOYEE_SQL,
            (employee.id, employee.name, employee.position,
             employee.department, employee.salary),
        )
        conn.commit()
        conn.close()
        return {'message': 'Employee added successfully'}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail='Employee ID already exists')
    except Exception:
        conn.close()
        raise HTTPException(status_code=500, detail='Internal server error')


@app.delete('/employees/{employee_id}')
@limiter.limit('30/minute')
async def delete_employee(employee_id: int, credentials: HTTPBasicCredentials = Depends(security)):
    _verify_credentials(credentials)
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
