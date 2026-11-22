import sqlite3

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

DB_PATH = 'employees.db'
EMPLOYEE_COLUMNS = ['id', 'name', 'position', 'department', 'salary']

CREATE_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT,
            department TEXT,
            salary REAL
        )
    '''

INSERT_EMPLOYEE_SQL = '''
        INSERT INTO employees (id, name, position, department, salary)
        VALUES (?, ?, ?, ?, ?)
    '''

INSERT_OR_IGNORE_EMPLOYEE_SQL = '''
        INSERT OR IGNORE INTO employees (id, name, position, department, salary)
        VALUES (?, ?, ?, ?, ?)
    '''

SEED_EMPLOYEES = [
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
]

app = FastAPI()


class Employee(BaseModel):
    id: int
    name: str
    position: str
    department: str
    salary: float


def _connect():
    """Open a new connection to the employees database."""
    return sqlite3.connect(DB_PATH)


def _rows_to_dicts(rows):
    """Convert database rows into dictionaries keyed by column name."""
    return [dict(zip(EMPLOYEE_COLUMNS, row)) for row in rows]


def init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    conn.close()


@app.on_event('startup')
def startup():
    init_db()
    conn = _connect()
    cursor = conn.cursor()
    cursor.executemany(INSERT_OR_IGNORE_EMPLOYEE_SQL, SEED_EMPLOYEES)
    conn.commit()
    conn.close()


@app.get('/employees/')
def get_all_employees():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employees')
    employees = cursor.fetchall()
    conn.close()
    return _rows_to_dicts(employees)


@app.get('/employees/filter/')
def get_employee_by_filter(
    filter_type: str = Query(..., description='Filter type (name, position, department)'),
    filter_value: str = Query(..., description='Value to filter by'),
):
    conn = _connect()
    cursor = conn.cursor()
    # NOTE: the query is built by string interpolation, which is vulnerable to
    # SQL injection. It is intentionally left unchanged to preserve existing
    # behaviour; it should be addressed separately.
    query = f"SELECT * FROM employees WHERE {filter_type} = '{filter_value}'"
    try:
        cursor.execute(query)
        employees = cursor.fetchall()
        conn.close()
        if not employees:
            # Note: this is caught by the handler below and re-raised as a 400,
            # which is the module's existing behaviour.
            raise HTTPException(status_code=404, detail='No employees found')
        return _rows_to_dicts(employees)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@app.post('/employees/')
def add_employee(employee: Employee):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        INSERT_EMPLOYEE_SQL,
        (employee.id, employee.name, employee.position, employee.department, employee.salary),
    )
    conn.commit()
    conn.close()
    return {'message': 'Employee added successfully'}


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int):
    conn = _connect()
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
