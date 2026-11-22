import sqlite3

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

DATABASE_PATH = 'employees.db'

CREATE_DEPARTMENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    )
"""

CREATE_EMPLOYEES_TABLE = """
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        department_id INTEGER,
        salary REAL,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    )
"""

INSERT_DEPARTMENT = 'INSERT INTO departments (name) VALUES (?)'
INSERT_EMPLOYEE = (
    'INSERT INTO employees (name, email, department_id, salary) '
    'VALUES (?, ?, ?, ?)'
)
SELECT_EMPLOYEE_BY_ID = 'SELECT * FROM employees WHERE id = ?'
DELETE_EMPLOYEE_BY_ID = 'DELETE FROM employees WHERE id = ?'

app = FastAPI()


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(CREATE_DEPARTMENTS_TABLE)
    cursor.execute(CREATE_EMPLOYEES_TABLE)
    conn.commit()
    conn.close()


class EmployeeCreate(BaseModel):
    name: str
    email: str
    department_id: int
    salary: float


class DepartmentCreate(BaseModel):
    name: str


@app.post('/departments/')
def create_department(department: DepartmentCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(INSERT_DEPARTMENT, (department.name,))
    db.commit()
    return {'message': 'Department created successfully'}


@app.post('/employees/')
def create_employee(employee: EmployeeCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        INSERT_EMPLOYEE,
        (employee.name, employee.email, employee.department_id, employee.salary),
    )
    db.commit()
    return {'message': 'Employee created successfully'}


def _build_search_query(search_query):
    # NOTE: the search term is interpolated directly into the SQL string.
    # This is preserved from the original implementation to keep behaviour
    # identical, but it is vulnerable to SQL injection.
    return (
        f"SELECT * FROM employees WHERE name LIKE '%{search_query}%' "
        f"OR email LIKE '%{search_query}%'"
    )


@app.get('/employees/search/')
def search_employees(request: Request, db: sqlite3.Connection = Depends(get_db)):
    search_query = request.query_params.get('query', '')
    if not search_query:
        raise HTTPException(status_code=400, detail='Search query parameter is required')

    cursor = db.cursor()
    cursor.execute(_build_search_query(search_query))
    employees = [dict(row) for row in cursor.fetchall()]
    return JSONResponse(content=employees)


@app.get('/employees/{employee_id}')
def get_employee(employee_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(SELECT_EMPLOYEE_BY_ID, (employee_id,))
    employee = cursor.fetchone()
    if not employee:
        raise HTTPException(status_code=404, detail='Employee not found')
    return dict(employee)


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(DELETE_EMPLOYEE_BY_ID, (employee_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


if __name__ == '__main__':
    init_db()
    uvicorn.run(app, host='0.0.0.0', port=8000)
