import json
import sqlite3
from datetime import datetime

import cherrypy

DATABASE_PATH = 'reports.db'

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS departments
        (id INTEGER PRIMARY KEY,
         name TEXT NOT NULL)
    """,
    """
    CREATE TABLE IF NOT EXISTS employees
        (id INTEGER PRIMARY KEY,
         name TEXT NOT NULL,
         department_id INTEGER,
         salary REAL,
         FOREIGN KEY(department_id) REFERENCES departments(id))
    """,
    """
    CREATE TABLE IF NOT EXISTS reports
        (id INTEGER PRIMARY KEY,
         title TEXT NOT NULL,
         content TEXT,
         created_by INTEGER,
         created_at DATETIME,
         FOREIGN KEY(created_by) REFERENCES employees(id))
    """,
)

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

COUNT_DEPARTMENTS = 'SELECT COUNT(*) FROM departments'

INSERT_DEPARTMENT = 'INSERT INTO departments VALUES (?, ?)'
INSERT_EMPLOYEE = 'INSERT INTO employees VALUES (?, ?, ?, ?)'
INSERT_REPORT = 'INSERT INTO reports VALUES (?, ?, ?, ?, ?)'

INSERT_NEW_REPORT = (
    'INSERT INTO reports (title, content, created_by, created_at) '
    'VALUES (?, ?, ?, ?)'
)

SELECT_REPORT_BY_ID = (
    'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
    'FROM reports r '
    'JOIN employees e ON r.created_by = e.id '
    'WHERE r.id = ?'
)

SELECT_REPORTS = (
    'SELECT r.id, r.title, e.name as author, d.name as department, '
    'r.created_at '
    'FROM reports r '
    'JOIN employees e ON r.created_by = e.id '
    'JOIN departments d ON e.department_id = d.id'
)


class ReportSystem:
    """CherryPy application that manages and queries company reports."""

    def __init__(self):
        self.init_db()

    def init_db(self):
        """Create the database schema and seed it when it is empty."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)

        cursor.execute(COUNT_DEPARTMENTS)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_DEPARTMENT, SEED_DEPARTMENTS)
            cursor.executemany(INSERT_EMPLOYEE, SEED_EMPLOYEES)
            cursor.executemany(INSERT_REPORT, SEED_REPORTS)
            conn.commit()

        conn.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        """Create a report from the given parameters and return its id."""
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])

            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute(
                INSERT_NEW_REPORT,
                (title, content, created_by, datetime.now()),
            )
            report_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return {'status': 'success', 'report_id': report_id}
        except Exception as e:
            raise cherrypy.HTTPError(400, str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_report(self, report_id):
        """Return the report with the given id, including its author."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(SELECT_REPORT_BY_ID, (report_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            raise cherrypy.HTTPError(404, 'Report not found')

        row_id, title, content, author, created_at = row
        return {
            'id': row_id,
            'title': title,
            'content': content,
            'author': author,
            'created_at': created_at,
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_report(self, **params):
        """Return reports filtered by department and/or creation date."""
        department = params.get('department')
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        conditions = []
        query_params = []
        if department:
            conditions.append('d.name = ?')
            query_params.append(department)
        if start_date:
            conditions.append('r.created_at >= ?')
            query_params.append(start_date)
        if end_date:
            conditions.append('r.created_at <= ?')
            query_params.append(end_date)

        query = SELECT_REPORTS
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY r.created_at DESC'

        cursor.execute(query, query_params)
        reports = [
            {
                'id': row_id,
                'title': title,
                'author': author,
                'department': department_name,
                'created_at': created_at,
            }
            for row_id, title, author, department_name, created_at
            in cursor.fetchall()
        ]
        conn.close()

        return {'reports': reports}


if __name__ == '__main__':
    cherrypy.quickstart(
        ReportSystem(),
        '/',
        {
            '/': {
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [
                    ('Content-Type', 'application/json'),
                ],
            },
        },
    )
