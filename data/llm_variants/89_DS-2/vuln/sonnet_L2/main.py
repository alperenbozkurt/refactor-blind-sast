import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Sequence, Tuple

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
DB_PATH = 'employees.db'
EMPLOYEE_COLUMNS = ['id', 'name', 'position', 'department', 'salary']

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

CREATE_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS employees (\n            id INTEGER PRIMARY KEY,\n            name TEXT NOT NULL,\n            position TEXT,\n            department TEXT,\n            salary REAL\n        )\n    '
INSERT_EMPLOYEE_SQL = '\n        INSERT INTO employees (id, name, position, department, salary)\n        VALUES (?, ?, ?, ?, ?)\n    '
INSERT_OR_IGNORE_EMPLOYEE_SQL = '\n        INSERT OR IGNORE INTO employees (id, name, position, department, salary)\n        VALUES (?, ?, ?, ?, ?)\n    '
SELECT_ALL_SQL = 'SELECT * FROM employees'
DELETE_EMPLOYEE_SQL = 'DELETE FROM employees WHERE id = ?'

SEED_EMPLOYEES: List[Tuple[Any, ...]] = [
    (1, 'John Doe', 'Developer', 'IT', 75000),
    (2, 'Jane Smith', 'Manager', 'HR', 90000),
    (3, 'Bob Johnson', 'Analyst', 'Finance', 80000),
]

MSG_NO_EMPLOYEES_FOUND = 'No employees found'
MSG_EMPLOYEE_NOT_FOUND = 'Employee not found'
MSG_EMPLOYEE_ADDED = 'Employee added successfully'
MSG_EMPLOYEE_DELETED = 'Employee deleted successfully'

FILTER_TYPE_DESCRIPTION = 'Filter type (name, position, department)'
FILTER_VALUE_DESCRIPTION = 'Value to filter by'

app = FastAPI()


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class Employee(BaseModel):
    id: int
    name: str
    position: str
    department: str
    salary: float


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    """Open a connection to the employee database and always close it."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _rows_to_dicts(rows: Sequence[Sequence[Any]]) -> List[Dict[str, Any]]:
    return [dict(zip(EMPLOYEE_COLUMNS, row)) for row in rows]


def _employee_to_params(employee: Employee) -> Tuple[Any, ...]:
    return (
        employee.id,
        employee.name,
        employee.position,
        employee.department,
        employee.salary,
    )


def _build_filter_query(filter_type: str, filter_value: str) -> str:
    # NOTE: built by string interpolation to preserve the original behaviour.
    return f"SELECT * FROM employees WHERE {filter_type} = '{filter_value}'"


def _seed_employees() -> None:
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(INSERT_OR_IGNORE_EMPLOYEE_SQL, SEED_EMPLOYEES)
        conn.commit()


def init_db():
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.on_event('startup')
def startup():
    init_db()
    _seed_employees()


@app.get('/employees/')
def get_all_employees():
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_SQL)
        employees = cursor.fetchall()
    return _rows_to_dicts(employees)


@app.get('/employees/filter/')
def get_employee_by_filter(
    filter_type: str = Query(..., description=FILTER_TYPE_DESCRIPTION),
    filter_value: str = Query(..., description=FILTER_VALUE_DESCRIPTION),
):
    with _connection() as conn:
        cursor = conn.cursor()
        query = _build_filter_query(filter_type, filter_value)
        try:
            cursor.execute(query)
            employees = cursor.fetchall()
            if not employees:
                # Note: as in the original, this is caught below and re-raised as 400.
                raise HTTPException(status_code=404, detail=MSG_NO_EMPLOYEES_FOUND)
            return _rows_to_dicts(employees)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.post('/employees/')
def add_employee(employee: Employee):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(INSERT_EMPLOYEE_SQL, _employee_to_params(employee))
        conn.commit()
    return {'message': MSG_EMPLOYEE_ADDED}


@app.delete('/employees/{employee_id}')
def delete_employee(employee_id: int):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(DELETE_EMPLOYEE_SQL, (employee_id,))
        conn.commit()
        affected = cursor.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail=MSG_EMPLOYEE_NOT_FOUND)
    return {'message': MSG_EMPLOYEE_DELETED}


def main() -> None:
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
