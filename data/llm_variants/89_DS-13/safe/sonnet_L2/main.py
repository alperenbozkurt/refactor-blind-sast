from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
import sqlite3
import uvicorn
from pydantic import BaseModel
import re

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

DATABASE_PATH = 'employees.db'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
SEARCH_FORBIDDEN_CHARS_PATTERN = re.compile(r'[;\'"\\]')

CREATE_DEPARTMENTS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS departments (\n            id INTEGER PRIMARY KEY,\n            name TEXT NOT NULL\n        )\n    '
CREATE_EMPLOYEES_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS employees (\n            id INTEGER PRIMARY KEY,\n            name TEXT NOT NULL,\n            email TEXT UNIQUE NOT NULL,\n            department_id INTEGER,\n            salary REAL,\n            FOREIGN KEY (department_id) REFERENCES departments(id)\n        )\n    '

INSERT_DEPARTMENT_SQL = 'INSERT INTO departments (name) VALUES (?)'
SELECT_DEPARTMENT_EXISTS_SQL = 'SELECT 1 FROM departments WHERE id = ?'
INSERT_EMPLOYEE_SQL = 'INSERT INTO employees (name, email, department_id, salary) VALUES (?, ?, ?, ?)'
SEARCH_EMPLOYEES_SQL = '\n        SELECT * FROM employees \n        WHERE name LIKE ? OR email LIKE ?\n    '
SELECT_EMPLOYEE_BY_ID_SQL = 'SELECT * FROM employees WHERE id = ?'
DELETE_EMPLOYEE_SQL = 'DELETE FROM employees WHERE id = ?'

SEARCH_QUERY_PARAM = 'query'

# Error / response messages
MSG_INVALID_EMAIL = 'Invalid email format'
MSG_INVALID_SALARY = 'Salary must be positive'
MSG_DEPARTMENT_NAME_EMPTY = 'Department name cannot be empty'
MSG_DEPARTMENT_EXISTS = 'Department already exists'
MSG_DEPARTMENT_CREATE_FAILED = 'Failed to create department'
MSG_DEPARTMENT_CREATED = 'Department created successfully'
MSG_DEPARTMENT_MISSING = 'Department does not exist'
MSG_EMAIL_EXISTS = 'Email already exists'
MSG_EMPLOYEE_CREATE_FAILED = 'Failed to create employee'
MSG_EMPLOYEE_CREATED = 'Employee created successfully'
MSG_SEARCH_QUERY_REQUIRED = 'Search query parameter is required'
MSG_EMPLOYEE_NOT_FOUND = 'Employee not found'
MSG_EMPLOYEE_DELETED = 'Employee deleted successfully'

app = FastAPI()


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(CREATE_DEPARTMENTS_TABLE_SQL)
    cursor.execute(CREATE_EMPLOYEES_TABLE_SQL)
    conn.commit()
    conn.close()


def _department_exists(cursor, department_id):
    cursor.execute(SELECT_DEPARTMENT_EXISTS_SQL, (department_id,))
    return bool(cursor.fetchone())


def _insert_employee(cursor, employee):
    cursor.execute(
        INSERT_EMPLOYEE_SQL,
        (employee.name, employee.email, employee.department_id, employee.salary),
    )


def _search_employees(cursor, search_query):
    pattern = f'%{search_query}%'
    cursor.execute(SEARCH_EMPLOYEES_SQL, (pattern, pattern))
    return [dict(row) for row in cursor.fetchall()]


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class EmployeeCreate(BaseModel):
    name: str
    email: str
    department_id: int
    salary: float


class DepartmentCreate(BaseModel):
    name: str


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #

def validate_email(email: str) -> str:
    if not EMAIL_PATTERN.match(email):
        raise ValueError(MSG_INVALID_EMAIL)
    return email


def validate_salary(salary: float) -> float:
    if salary <= 0:
        raise ValueError(MSG_INVALID_SALARY)
    return salary


def sanitize_search_term(term: str) -> str:
    if not term:
        return ''
    return SEARCH_FORBIDDEN_CHARS_PATTERN.sub('', term)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.post('/departments/')
def create_department(department: DepartmentCreate, db: sqlite3.Connection=Depends(get_db)):
    if not department.name.strip():
        raise HTTPException(status_code=400, detail=MSG_DEPARTMENT_NAME_EMPTY)
    cursor = db.cursor()
    try:
        cursor.execute(INSERT_DEPARTMENT_SQL, (department.name,))
        db.commit()
        return {'message': MSG_DEPARTMENT_CREATED}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=MSG_DEPARTMENT_EXISTS)
    except Exception:
        raise HTTPException(status_code=500, detail=MSG_DEPARTMENT_CREATE_FAILED)


@app.post('/employees/')
def create_employee(employee: EmployeeCreate, db: sqlite3.Connection=Depends(get_db)):
    try:
        validate_email(employee.email)
        validate_salary(employee.salary)
        cursor = db.cursor()
        if not _department_exists(cursor, employee.department_id):
            # Note: this HTTPException is caught by the generic handler below,
            # which preserves the original (500) behaviour.
            raise HTTPException(status_code=400, detail=MSG_DEPARTMENT_MISSING)
        _insert_employee(cursor, employee)
        db.commit()
        return {'message': MSG_EMPLOYEE_CREATED}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=MSG_EMAIL_EXISTS)
    except Exception:
        raise HTTPException(status_code=500, detail=MSG_EMPLOYEE_CREATE_FAILED)


@app.get('/employees/search/')
def search_employees(request: Request, db: sqlite3.Connection=Depends(get_db)):
    search_query = sanitize_search_term(request.query_params.get(SEARCH_QUERY_PARAM, ''))
    if not search_query:
        raise HTTPException(status_code=400, detail=MSG_SEARCH_QUERY_REQUIRED)
    cursor = db.cursor()
    employees = _search_employees(cursor, search_query)
    return JSONResponse(content=employees)


@app.get('/employees/{employee_id}')
def get_employee(employee_id: int, db: sqlite3.Connection=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(SELECT_EMPLOYEE_BY_ID_SQL, (employee_id,))
    employee = cursor.fetchone()
    if not employee:
        raise HTTPException(status_code=404, detail=MSG_EMPLOYEE_NOT_FOUND)
    return dict(employee)


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int, db: sqlite3.Connection=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(DELETE_EMPLOYEE_SQL, (employee_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=MSG_EMPLOYEE_NOT_FOUND)
    return {'message': MSG_EMPLOYEE_DELETED}


def main():
    init_db()
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
