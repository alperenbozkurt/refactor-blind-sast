"""CherryPy web service for creating, fetching and generating employee reports."""

import cherrypy
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime

DATABASE_PATH = 'reports.db'

CHERRYPY_CONFIG = {
    '/': {
        'tools.response_headers.on': True,
        'tools.response_headers.headers': [('Content-Type', 'application/json')],
    }
}

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        department_id INTEGER,
        salary REAL,
        FOREIGN KEY(department_id) REFERENCES departments(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT,
        created_by INTEGER,
        created_at DATETIME,
        FOREIGN KEY(created_by) REFERENCES employees(id)
    )
    """,
)

_COUNT_DEPARTMENTS = 'SELECT COUNT(*) FROM departments'

_INSERT_DEPARTMENT = 'INSERT INTO departments VALUES (?, ?)'
_INSERT_EMPLOYEE = 'INSERT INTO employees VALUES (?, ?, ?, ?)'
_INSERT_SEED_REPORT = 'INSERT INTO reports VALUES (?, ?, ?, ?, ?)'
_INSERT_REPORT = (
    'INSERT INTO reports (title, content, created_by, created_at) '
    'VALUES (?, ?, ?, ?)'
)

_SELECT_REPORT = (
    'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
    'FROM reports r '
    'JOIN employees e ON r.created_by = e.id '
    'WHERE r.id = ?'
)

_SELECT_REPORTS = (
    'SELECT r.id, r.title, e.name as author, d.name as department, r.created_at '
    'FROM reports r '
    'JOIN employees e ON r.created_by = e.id '
    'JOIN departments d ON e.department_id = d.id'
)

_REPORTS_ORDER = ' ORDER BY r.created_at DESC'

# Maps generate_report query-string parameters to their SQL filter clauses.
_REPORT_FILTERS = (
    ('department', 'd.name = ?'),
    ('start_date', 'r.created_at >= ?'),
    ('end_date', 'r.created_at <= ?'),
)

_SEED_DEPARTMENTS = (
    (1, 'HR'),
    (2, 'Engineering'),
    (3, 'Finance'),
)

_SEED_EMPLOYEES = (
    (1, 'Alice Smith', 1, 65000),
    (2, 'Bob Johnson', 2, 85000),
    (3, 'Carol Williams', 3, 75000),
)

_SEED_REPORTS = (
    (1, 'Q1 Hiring Report', 'Hired 5 new engineers', 1, '2023-01-15'),
    (2, 'System Upgrade', 'Updated all servers', 2, '2023-02-20'),
)


@contextmanager
def _db_connection():
    """Yield a connection to the reports database, closing it afterwards."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _seed_database(cursor):
    """Populate an empty database with the default rows."""
    cursor.executemany(_INSERT_DEPARTMENT, _SEED_DEPARTMENTS)
    cursor.executemany(_INSERT_EMPLOYEE, _SEED_EMPLOYEES)
    cursor.executemany(_INSERT_SEED_REPORT, _SEED_REPORTS)


def _build_reports_query(params):
    """Build the filtered reports query and its bound parameter list."""
    conditions = []
    values = []
    for param_name, clause in _REPORT_FILTERS:
        value = params.get(param_name)
        if value:
            conditions.append(clause)
            values.append(value)
    query = _SELECT_REPORTS
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    return query + _REPORTS_ORDER, values


def _report_details(row):
    """Map a joined report row to its JSON representation."""
    return {
        'id': row[0],
        'title': row[1],
        'content': row[2],
        'author': row[3],
        'created_at': row[4],
    }


def _report_summary(row):
    """Map an aggregated report row to its JSON representation."""
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'department': row[3],
        'created_at': row[4],
    }


class ReportSystem:

    def __init__(self):
        self.init_db()

    def init_db(self):
        with _db_connection() as conn:
            cursor = conn.cursor()
            for statement in _SCHEMA_STATEMENTS:
                cursor.execute(statement)
            cursor.execute(_COUNT_DEPARTMENTS)
            if cursor.fetchone()[0] == 0:
                _seed_database(cursor)
                conn.commit()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])
            with _db_connection() as conn:
                cursor = conn.execute(
                    _INSERT_REPORT, (title, content, created_by, datetime.now())
                )
                report_id = cursor.lastrowid
                conn.commit()
            return {'status': 'success', 'report_id': report_id}
        except Exception as e:
            raise cherrypy.HTTPError(400, str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_report(self, report_id):
        with _db_connection() as conn:
            report = conn.execute(_SELECT_REPORT, (report_id,)).fetchone()
        if report:
            return _report_details(report)
        raise cherrypy.HTTPError(404, 'Report not found')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_report(self, **params):
        query, values = _build_reports_query(params)
        with _db_connection() as conn:
            rows = conn.execute(query, values).fetchall()
        return {'reports': [_report_summary(row) for row in rows]}


def main():
    cherrypy.quickstart(ReportSystem(), '/', CHERRYPY_CONFIG)


if __name__ == '__main__':
    main()
