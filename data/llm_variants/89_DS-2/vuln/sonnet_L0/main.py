import sqlite3
from contextlib import closing

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

DB_PATH = 'employees.db'
COLUMNS = ['id', 'name', 'position', 'department', 'salary']

SEED_EMPLOYEES = [
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
]

CREATE_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        position TEXT,
        department TEXT,
        salary REAL
    )
'''

INSERT_SQL = '''
    INSERT INTO employees (id, name, position, department, salary)
    VALUES (?, ?, ?, ?, ?)
'''

INSERT_OR_IGNORE_SQL = INSERT_SQL.replace('INSERT INTO', 'INSERT OR IGNORE INTO')

app = FastAPI()


class Employee(BaseModel):
    id: int
    name: str
    position: str
    department: str
    salary: float


def _connect():
    """Return a connection that is closed when used in a `with closing(...)` block."""
    return closing(sqlite3.connect(DB_PATH))


def _rows_to_dicts(rows):
    return [dict(zip(COLUMNS, row)) for row in rows]


def init_db():
    with _connect() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


@app.on_event('startup')
def startup():
    init_db()
    with _connect() as conn:
        conn.executemany(INSERT_OR_IGNORE_SQL, SEED_EMPLOYEES)
        conn.commit()


@app.get('/employees/')
def get_all_employees():
    with _connect() as conn:
        rows = conn.execute('SELECT * FROM employees').fetchall()
    return _rows_to_dicts(rows)


@app.get('/employees/filter/')
def get_employee_by_filter(
    filter_type: str = Query(..., description='Filter type (name, position, department)'),
    filter_value: str = Query(..., description='Value to filter by'),
):
    if filter_type not in COLUMNS:
        raise HTTPException(status_code=400, detail=f'no such column: {filter_type}')

    query = f'SELECT * FROM employees WHERE {filter_type} = ?'
    try:
        with _connect() as conn:
            employees = conn.execute(query, (filter_value,)).fetchall()
    except sqlite3.Error as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not employees:
        # Preserves the original response: the 404 was caught and re-raised as a 400.
        raise HTTPException(status_code=400, detail='404: No employees found')
    return _rows_to_dicts(employees)


@app.post('/employees/')
def add_employee(employee: Employee):
    with _connect() as conn:
        conn.execute(
            INSERT_SQL,
            (employee.id, employee.name, employee.position, employee.department, employee.salary),
        )
        conn.commit()
    return {'message': 'Employee added successfully'}


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int):
    with _connect() as conn:
        cursor = conn.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
        conn.commit()
        affected = cursor.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
