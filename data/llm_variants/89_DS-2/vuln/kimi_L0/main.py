import sqlite3
from contextlib import closing

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

DATABASE_PATH = 'employees.db'
EMPLOYEE_COLUMNS = ('id', 'name', 'position', 'department', 'salary')

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

SEED_EMPLOYEES = [
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
]

INSERT_EMPLOYEE_SQL = """
        INSERT INTO employees (id, name, position, department, salary)
        VALUES (?, ?, ?, ?, ?)
    """

SELECT_ALL_EMPLOYEES_SQL = 'SELECT * FROM employees'
DELETE_EMPLOYEE_SQL = 'DELETE FROM employees WHERE id = ?'

app = FastAPI()


class Employee(BaseModel):
    id: int
    name: str
    position: str
    department: str
    salary: float


def _get_connection():
    return sqlite3.connect(DATABASE_PATH)


def _rows_to_dicts(rows):
    return [dict(zip(EMPLOYEE_COLUMNS, row)) for row in rows]


def init_db():
    with closing(_get_connection()) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


@app.on_event('startup')
def startup():
    init_db()
    with closing(_get_connection()) as conn:
        conn.executemany(SEED_EMPLOYEES_SQL, SEED_EMPLOYEES)
        conn.commit()


@app.get('/employees/')
def get_all_employees():
    with closing(_get_connection()) as conn:
        employees = conn.execute(SELECT_ALL_EMPLOYEES_SQL).fetchall()
    return _rows_to_dicts(employees)


@app.get('/employees/filter/')
def get_employee_by_filter(
    filter_type: str = Query(..., description='Filter type (name, position, department)'),
    filter_value: str = Query(..., description='Value to filter by'),
):
    conn = _get_connection()
    query = f"SELECT * FROM employees WHERE {filter_type} = '{filter_value}'"
    try:
        employees = conn.execute(query).fetchall()
        conn.close()
        if not employees:
            raise HTTPException(status_code=404, detail='No employees found')
        return _rows_to_dicts(employees)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@app.post('/employees/')
def add_employee(employee: Employee):
    with closing(_get_connection()) as conn:
        conn.execute(
            INSERT_EMPLOYEE_SQL,
            (employee.id, employee.name, employee.position, employee.department, employee.salary),
        )
        conn.commit()
    return {'message': 'Employee added successfully'}


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int):
    with closing(_get_connection()) as conn:
        cursor = conn.execute(DELETE_EMPLOYEE_SQL, (employee_id,))
        conn.commit()
        affected = cursor.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail='Employee not found')
    return {'message': 'Employee deleted successfully'}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
