from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
import sqlite3
import uvicorn
from pydantic import BaseModel
from typing import Optional
import secrets
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
DB_PATH = 'employees.db'
ALLOWED_HOSTS = ['example.com']
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'secret'

EMPLOYEE_COLUMNS = ['id', 'name', 'position', 'department', 'salary']
ALLOWED_FILTER_TYPES = {'name', 'position', 'department'}
MAX_FIELD_LENGTH = 100
MAX_FILTER_VALUE_LENGTH = 100

RATE_LIMIT_LIST = '100/minute'
RATE_LIMIT_FILTER = '60/minute'
RATE_LIMIT_WRITE = '30/minute'

CREATE_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS employees (\n            id INTEGER PRIMARY KEY,\n            name TEXT NOT NULL,\n            position TEXT,\n            department TEXT,\n            salary REAL\n        )\n    '
SEED_INSERT_SQL = '\n        INSERT OR IGNORE INTO employees (id, name, position, department, salary)\n        VALUES (?, ?, ?, ?, ?)\n    '
INSERT_EMPLOYEE_SQL = '\n            INSERT INTO employees (id, name, position, department, salary)\n            VALUES (?, ?, ?, ?, ?)\n        '
SELECT_ALL_SQL = 'SELECT * FROM employees'
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
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
security = HTTPBasic()


class Employee(BaseModel):
    id: int
    name: str
    position: str
    department: str
    salary: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _connect():
    return sqlite3.connect(DB_PATH)


@contextmanager
def _db_connection():
    """Yield an open connection and always close it afterwards."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def _rows_to_dicts(rows):
    return [dict(zip(EMPLOYEE_COLUMNS, row)) for row in rows]


def _verify_credentials(credentials: HTTPBasicCredentials):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail='Incorrect credentials',
            headers={'WWW-Authenticate': 'Basic'},
        )


def _validate_new_employee(employee: Employee):
    if employee.salary < 0:
        raise HTTPException(status_code=400, detail='Salary cannot be negative')
    if (
        len(employee.name) > MAX_FIELD_LENGTH
        or len(employee.position) > MAX_FIELD_LENGTH
        or len(employee.department) > MAX_FIELD_LENGTH
    ):
        raise HTTPException(status_code=400, detail='Field values too long')


def _sanitize_filter_value(value: str) -> str:
    return value.replace("'", "''")[:MAX_FILTER_VALUE_LENGTH]


def _employee_params(employee: Employee):
    return (employee.id, employee.name, employee.position, employee.department, employee.salary)


def init_db():
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()


def _seed_db():
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(SEED_INSERT_SQL, SEED_EMPLOYEES)
        conn.commit()


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------
@app.on_event('startup')
def startup():
    init_db()
    _seed_db()


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
@limiter.limit(RATE_LIMIT_LIST)
async def get_all_employees(credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_SQL)
        employees = cursor.fetchall()
    return _rows_to_dicts(employees)


@app.get('/employees/filter/')
@limiter.limit(RATE_LIMIT_FILTER)
async def get_employee_by_filter(filter_type: str=Query(..., description='Filter type (name, position, department)'), filter_value: str=Query(..., description='Value to filter by'), credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    if filter_type not in ALLOWED_FILTER_TYPES:
        raise HTTPException(status_code=400, detail='Invalid filter type')
    safe_filter_value = _sanitize_filter_value(filter_value)
    conn = _connect()
    cursor = conn.cursor()
    query = f'SELECT * FROM employees WHERE {filter_type} = ?'
    try:
        cursor.execute(query, (safe_filter_value,))
        employees = cursor.fetchall()
        conn.close()
        if not employees:
            # Note: preserved original behaviour - this is caught by the
            # generic handler below and surfaces as a 500 response.
            raise HTTPException(status_code=404, detail='No employees found')
        return _rows_to_dicts(employees)
    except sqlite3.Error:
        conn.close()
        raise HTTPException(status_code=400, detail='Database error')
    except Exception:
        conn.close()
        raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/employees/')
@limiter.limit(RATE_LIMIT_WRITE)
async def add_employee(employee: Employee, credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    _validate_new_employee(employee)
    conn = _connect()
    cursor = conn.cursor()
    try:
        cursor.execute(INSERT_EMPLOYEE_SQL, _employee_params(employee))
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
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_employee(employee_id: int, credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(DELETE_EMPLOYEE_SQL, (employee_id,))
        conn.commit()
        affected = cursor.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


if __name__ == '__main__':
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
