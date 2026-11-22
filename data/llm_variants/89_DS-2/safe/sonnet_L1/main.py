from contextlib import closing

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

DB_PATH = 'employees.db'
EMPLOYEE_COLUMNS = ['id', 'name', 'position', 'department', 'salary']
ALLOWED_FILTER_TYPES = {'name', 'position', 'department'}
MAX_FIELD_LENGTH = 100

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'secret'

SEED_EMPLOYEES = [
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
]

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


def _connect():
    """Open a database connection that is closed when used with `closing`."""
    return closing(sqlite3.connect(DB_PATH))


def _verify_credentials(credentials: HTTPBasicCredentials):
    """Raise a 401 error unless the supplied credentials are valid."""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail='Incorrect credentials',
            headers={'WWW-Authenticate': 'Basic'},
        )


def _rows_to_dicts(rows):
    return [dict(zip(EMPLOYEE_COLUMNS, row)) for row in rows]


def init_db():
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT,
            department TEXT,
            salary REAL
        )
    ''')
        conn.commit()


@app.on_event('startup')
def startup():
    init_db()
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.executemany('''
        INSERT OR IGNORE INTO employees (id, name, position, department, salary)
        VALUES (?, ?, ?, ?, ?)
    ''', SEED_EMPLOYEES)
        conn.commit()


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={'detail': 'Too many requests'},
        headers={'Retry-After': str(exc.retry_after)},
    )


@app.get('/employees/')
@limiter.limit('100/minute')
async def get_all_employees(credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM employees')
        employees = cursor.fetchall()
    return _rows_to_dicts(employees)


@app.get('/employees/filter/')
@limiter.limit('60/minute')
async def get_employee_by_filter(filter_type: str=Query(..., description='Filter type (name, position, department)'), filter_value: str=Query(..., description='Value to filter by'), credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    if filter_type not in ALLOWED_FILTER_TYPES:
        raise HTTPException(status_code=400, detail='Invalid filter type')
    safe_filter_value = filter_value.replace("'", "''")[:MAX_FIELD_LENGTH]
    query = f'SELECT * FROM employees WHERE {filter_type} = ?'
    with _connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, (safe_filter_value,))
            employees = cursor.fetchall()
            if not employees:
                # Note: raised inside the try block, so the generic handler
                # below converts it into a 500 (existing behaviour preserved).
                raise HTTPException(status_code=404, detail='No employees found')
            return _rows_to_dicts(employees)
        except sqlite3.Error:
            raise HTTPException(status_code=400, detail='Database error')
        except Exception:
            raise HTTPException(status_code=500, detail='Internal server error')


@app.post('/employees/')
@limiter.limit('30/minute')
async def add_employee(employee: Employee, credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    if employee.salary < 0:
        raise HTTPException(status_code=400, detail='Salary cannot be negative')
    if any(len(value) > MAX_FIELD_LENGTH for value in (employee.name, employee.position, employee.department)):
        raise HTTPException(status_code=400, detail='Field values too long')
    with _connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO employees (id, name, position, department, salary)
            VALUES (?, ?, ?, ?, ?)
        ''', (employee.id, employee.name, employee.position, employee.department, employee.salary))
            conn.commit()
            return {'message': 'Employee added successfully'}
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail='Employee ID already exists')
        except Exception:
            raise HTTPException(status_code=500, detail='Internal server error')


@app.delete('/employees/{employee_id}')
@limiter.limit('30/minute')
async def delete_employee(employee_id: int, credentials: HTTPBasicCredentials=Depends(security)):
    _verify_credentials(credentials)
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
        conn.commit()
        affected = cursor.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
