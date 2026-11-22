"""Report management web service.

A small CherryPy application backed by a SQLite database. It exposes
endpoints to create reports, retrieve a single report and generate
filtered report listings by department and creation date.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

import cherrypy

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'reports.db'

CHERRYPY_CONFIG = {
    '/': {
        'tools.response_headers.on': True,
        'tools.response_headers.headers': [('Content-Type', 'application/json')],
    },
}

# ---------------------------------------------------------------------------
# Database schema and queries
# ---------------------------------------------------------------------------

SCHEMA_STATEMENTS = (
    'CREATE TABLE IF NOT EXISTS departments '
    '(id INTEGER PRIMARY KEY, name TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS employees '
    '(id INTEGER PRIMARY KEY, name TEXT NOT NULL, department_id INTEGER, '
    'salary REAL, FOREIGN KEY(department_id) REFERENCES departments(id))',
    'CREATE TABLE IF NOT EXISTS reports '
    '(id INTEGER PRIMARY KEY, title TEXT NOT NULL, content TEXT, '
    'created_by INTEGER, created_at DATETIME, '
    'FOREIGN KEY(created_by) REFERENCES employees(id))',
)

COUNT_DEPARTMENTS_SQL = 'SELECT COUNT(*) FROM departments'

INSERT_DEPARTMENT_SQL = 'INSERT INTO departments VALUES (?, ?)'
INSERT_EMPLOYEE_SQL = 'INSERT INTO employees VALUES (?, ?, ?, ?)'
INSERT_SEED_REPORT_SQL = 'INSERT INTO reports VALUES (?, ?, ?, ?, ?)'

INSERT_REPORT_SQL = (
    'INSERT INTO reports (title, content, created_by, created_at) '
    'VALUES (?, ?, ?, ?)'
)

SELECT_REPORT_SQL = (
    'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
    'FROM reports r '
    'JOIN employees e ON r.created_by = e.id '
    'WHERE r.id = ?'
)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_DEPARTMENTS = (
    (1, 'HR'),
    (2, 'Engineering'),
    (3, 'Finance'),
)

SEED_EMPLOYEES = (
    (1, 'Alice Smith', 1, 65000),
    (2, 'Bob Johnson', 2, 85000),
    (3, 'Carol Williams', 3, 75000),
)

SEED_REPORTS = (
    (1, 'Q1 Hiring Report', 'Hired 5 new engineers', 1, '2023-01-15'),
    (2, 'System Upgrade', 'Updated all servers', 2, '2023-02-20'),
)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


@contextmanager
def _open_database(path: str = DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    """Yield an open SQLite connection, closing it when the block exits."""
    conn = sqlite3.connect(path)
    try:
        yield conn
    finally:
        conn.close()


def _build_report_query(department: Optional[str] = None,
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> str:
    """Build the ``generate_report`` query for the given filters.

    Filter values are interpolated into the SQL string to preserve the
    exact query semantics of the original implementation.
    """
    query = (
        'SELECT r.id, r.title, e.name as author, d.name as department, '
        'r.created_at '
        'FROM reports r '
        'JOIN employees e ON r.created_by = e.id '
        'JOIN departments d ON e.department_id = d.id '
    )
    conditions = []
    if department:
        conditions.append(f"d.name = '{department}'")
    if start_date:
        conditions.append(f"r.created_at >= '{start_date}'")
    if end_date:
        conditions.append(f"r.created_at <= '{end_date}'")
    if conditions:
        query += 'WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY r.created_at DESC'
    return query


def _report_detail(row: tuple) -> dict:
    """Map a ``SELECT_REPORT_SQL`` row to its JSON representation."""
    return {
        'id': row[0],
        'title': row[1],
        'content': row[2],
        'author': row[3],
        'created_at': row[4],
    }


def _report_summary(row: tuple) -> dict:
    """Map a ``generate_report`` query row to its JSON representation."""
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'department': row[3],
        'created_at': row[4],
    }


# ---------------------------------------------------------------------------
# Web application
# ---------------------------------------------------------------------------


class ReportSystem:
    """CherryPy root resource exposing the report endpoints."""

    def __init__(self):
        self.init_db()

    def init_db(self):
        """Create the database schema and seed it when it is empty."""
        with _open_database() as conn:
            cursor = conn.cursor()
            self._create_schema(cursor)
            if self._database_is_empty(cursor):
                self._seed_database(cursor)
                conn.commit()

    @staticmethod
    def _create_schema(cursor):
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)

    @staticmethod
    def _database_is_empty(cursor):
        cursor.execute(COUNT_DEPARTMENTS_SQL)
        return cursor.fetchone()[0] == 0

    @staticmethod
    def _seed_database(cursor):
        cursor.executemany(INSERT_DEPARTMENT_SQL, SEED_DEPARTMENTS)
        cursor.executemany(INSERT_EMPLOYEE_SQL, SEED_EMPLOYEES)
        cursor.executemany(INSERT_SEED_REPORT_SQL, SEED_REPORTS)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        """Create a new report and return its id."""
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])
            with _open_database() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    INSERT_REPORT_SQL,
                    (title, content, created_by, datetime.now()),
                )
                report_id = cursor.lastrowid
                conn.commit()
            return {'status': 'success', 'report_id': report_id}
        except Exception as e:
            raise cherrypy.HTTPError(400, str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_report(self, report_id):
        """Return a single report, or 404 if it does not exist."""
        with _open_database() as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_REPORT_SQL, (report_id,))
            report = cursor.fetchone()
        if report:
            return _report_detail(report)
        raise cherrypy.HTTPError(404, 'Report not found')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_report(self, **params):
        """Return reports filtered by department and/or creation date."""
        query = _build_report_query(
            department=params.get('department'),
            start_date=params.get('start_date'),
            end_date=params.get('end_date'),
        )
        with _open_database() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            reports = [_report_summary(row) for row in cursor.fetchall()]
        return {'reports': reports}


def main():
    """Start the CherryPy server with the configured application."""
    cherrypy.quickstart(ReportSystem(), '/', CHERRYPY_CONFIG)


if __name__ == '__main__':
    main()
