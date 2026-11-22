from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
import sqlite3
import uvicorn
from pydantic import BaseModel


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class Config:
    DB_PATH = 'employees.db'
    HOST = '0.0.0.0'
    PORT = 8000


SEARCH_QUERY_PARAM = 'query'

MSG_DEPARTMENT_CREATED = 'Department created successfully'
MSG_EMPLOYEE_CREATED = 'Employee created successfully'
MSG_EMPLOYEE_DELETED = 'Employee deleted successfully'
MSG_EMPLOYEE_NOT_FOUND = 'Employee not found'
MSG_SEARCH_QUERY_REQUIRED = 'Search query parameter is required'


# --------------------------------------------------------------------------- #
# SQL statements
# --------------------------------------------------------------------------- #
CREATE_DEPARTMENTS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    '''

CREATE_EMPLOYEES_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department_id INTEGER,
            salary REAL,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    '''

INSERT_DEPARTMENT_SQL = 'INSERT INTO departments (name) VALUES (?)'
INSERT_EMPLOYEE_SQL = (
    'INSERT INTO employees (name, email, department_id, salary) '
    'VALUES (?, ?, ?, ?)'
)
# Parameterized (instead of string-interpolated) to avoid SQL injection.
SEARCH_EMPLOYEES_SQL = (
    'SELECT * FROM employees WHERE name LIKE ? OR email LIKE ?'
)
SELECT_EMPLOYEE_SQL = 'SELECT * FROM employees WHERE id = ?'
DELETE_EMPLOYEE_SQL = 'DELETE FROM employees WHERE id = ?'


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
def get_db():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(CREATE_DEPARTMENTS_TABLE_SQL)
    cursor.execute(CREATE_EMPLOYEES_TABLE_SQL)
    conn.commit()
    conn.close()


def _row_to_dict(row):
    return dict(row)


def _build_like_pattern(term):
    return f'%{term}%'


def _employee_not_found():
    return HTTPException(status_code=404, detail=MSG_EMPLOYEE_NOT_FOUND)


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
# Application and routes
# --------------------------------------------------------------------------- #
app = FastAPI()


@app.post('/departments/')
def create_department(department: DepartmentCreate, db: sqlite3.Connection=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(INSERT_DEPARTMENT_SQL, (department.name,))
    db.commit()
    return {'message': MSG_DEPARTMENT_CREATED}


@app.post('/employees/')
def create_employee(employee: EmployeeCreate, db: sqlite3.Connection=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        INSERT_EMPLOYEE_SQL,
        (employee.name, employee.email, employee.department_id, employee.salary),
    )
    db.commit()
    return {'message': MSG_EMPLOYEE_CREATED}


@app.get('/employees/search/')
def search_employees(request: Request, db: sqlite3.Connection=Depends(get_db)):
    search_query = request.query_params.get(SEARCH_QUERY_PARAM, '')
    if not search_query:
        raise HTTPException(status_code=400, detail=MSG_SEARCH_QUERY_REQUIRED)
    pattern = _build_like_pattern(search_query)
    cursor = db.cursor()
    cursor.execute(SEARCH_EMPLOYEES_SQL, (pattern, pattern))
    employees = [_row_to_dict(row) for row in cursor.fetchall()]
    return JSONResponse(content=employees)


@app.get('/employees/{employee_id}')
def get_employee(employee_id: int, db: sqlite3.Connection=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(SELECT_EMPLOYEE_SQL, (employee_id,))
    employee = cursor.fetchone()
    if not employee:
        raise _employee_not_found()
    return _row_to_dict(employee)


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int, db: sqlite3.Connection=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(DELETE_EMPLOYEE_SQL, (employee_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise _employee_not_found()
    return {'message': MSG_EMPLOYEE_DELETED}


def main():
    init_db()
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)


if __name__ == '__main__':
    main()
