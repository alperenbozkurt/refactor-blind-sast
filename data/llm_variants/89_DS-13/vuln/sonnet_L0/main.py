from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
import sqlite3
import uvicorn
from pydantic import BaseModel

DATABASE_PATH = 'employees.db'

CREATE_DEPARTMENTS_TABLE = '''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    '''

CREATE_EMPLOYEES_TABLE = '''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department_id INTEGER,
            salary REAL,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    '''

app = FastAPI()


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_DEPARTMENTS_TABLE)
        cursor.execute(CREATE_EMPLOYEES_TABLE)
        conn.commit()
    finally:
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
    db.execute('INSERT INTO departments (name) VALUES (?)', (department.name,))
    db.commit()
    return {'message': 'Department created successfully'}


@app.post('/employees/')
def create_employee(employee: EmployeeCreate, db: sqlite3.Connection = Depends(get_db)):
    db.execute(
        'INSERT INTO employees (name, email, department_id, salary) VALUES (?, ?, ?, ?)',
        (employee.name, employee.email, employee.department_id, employee.salary),
    )
    db.commit()
    return {'message': 'Employee created successfully'}


@app.get('/employees/search/')
def search_employees(request: Request, db: sqlite3.Connection = Depends(get_db)):
    search_query = request.query_params.get('query', '')
    if not search_query:
        raise HTTPException(status_code=400, detail='Search query parameter is required')

    # Parameterized query (avoids SQL injection); same matching for normal input.
    pattern = f'%{search_query}%'
    rows = db.execute(
        'SELECT * FROM employees WHERE name LIKE ? OR email LIKE ?',
        (pattern, pattern),
    ).fetchall()
    return JSONResponse(content=[dict(row) for row in rows])


@app.get('/employees/{employee_id}')
def get_employee(employee_id: int, db: sqlite3.Connection = Depends(get_db)):
    employee = db.execute(
        'SELECT * FROM employees WHERE id = ?', (employee_id,)
    ).fetchone()
    if not employee:
        raise HTTPException(status_code=404, detail='Employee not found')
    return dict(employee)


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


if __name__ == '__main__':
    init_db()
    uvicorn.run(app, host='0.0.0.0', port=8000)
