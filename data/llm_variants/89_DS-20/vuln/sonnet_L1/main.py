import sqlite3
from contextlib import closing
from datetime import datetime

import cherrypy
import json  # noqa: F401  (kept to preserve the module's original namespace)

DB_PATH = 'reports.db'

CREATE_DEPARTMENTS_SQL = (
    'CREATE TABLE IF NOT EXISTS departments\n'
    '                     (id INTEGER PRIMARY KEY,\n'
    '                     name TEXT NOT NULL)'
)
CREATE_EMPLOYEES_SQL = (
    'CREATE TABLE IF NOT EXISTS employees\n'
    '                     (id INTEGER PRIMARY KEY,\n'
    '                     name TEXT NOT NULL,\n'
    '                     department_id INTEGER,\n'
    '                     salary REAL,\n'
    '                     FOREIGN KEY(department_id) REFERENCES departments(id))'
)
CREATE_REPORTS_SQL = (
    'CREATE TABLE IF NOT EXISTS reports\n'
    '                     (id INTEGER PRIMARY KEY,\n'
    '                     title TEXT NOT NULL,\n'
    '                     content TEXT,\n'
    '                     created_by INTEGER,\n'
    '                     created_at DATETIME,\n'
    '                     FOREIGN KEY(created_by) REFERENCES employees(id))'
)

SEED_DEPARTMENTS = [(1, 'HR'), (2, 'Engineering'), (3, 'Finance')]
SEED_EMPLOYEES = [
    (1, 'Alice Smith', 1, 65000),
    (2, 'Bob Johnson', 2, 85000),
    (3, 'Carol Williams', 3, 75000),
]
SEED_REPORTS = [
    (1, 'Q1 Hiring Report', 'Hired 5 new engineers', 1, '2023-01-15'),
    (2, 'System Upgrade', 'Updated all servers', 2, '2023-02-20'),
]


def _connect():
    """Open a new connection to the reports database."""
    return sqlite3.connect(DB_PATH)


class ReportSystem:

    def __init__(self):
        self.init_db()

    def init_db(self):
        with closing(_connect()) as conn:
            c = conn.cursor()
            self._create_tables(c)
            self._seed_if_empty(c)
            conn.commit()

    @staticmethod
    def _create_tables(c):
        c.execute(CREATE_DEPARTMENTS_SQL)
        c.execute(CREATE_EMPLOYEES_SQL)
        c.execute(CREATE_REPORTS_SQL)

    @staticmethod
    def _seed_if_empty(c):
        c.execute('SELECT COUNT(*) FROM departments')
        if c.fetchone()[0] != 0:
            return
        c.executemany('INSERT INTO departments VALUES (?, ?)', SEED_DEPARTMENTS)
        c.executemany('INSERT INTO employees VALUES (?, ?, ?, ?)', SEED_EMPLOYEES)
        c.executemany('INSERT INTO reports VALUES (?, ?, ?, ?, ?)', SEED_REPORTS)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])
            with closing(_connect()) as conn:
                c = conn.cursor()
                c.execute(
                    'INSERT INTO reports (title, content, created_by, created_at) VALUES (?, ?, ?, ?)',
                    (title, content, created_by, datetime.now()),
                )
                report_id = c.lastrowid
                conn.commit()
            return {'status': 'success', 'report_id': report_id}
        except Exception as e:
            raise cherrypy.HTTPError(400, str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_report(self, report_id):
        with closing(_connect()) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
                'FROM reports r JOIN employees e ON r.created_by = e.id WHERE r.id = ?',
                (report_id,),
            )
            report = c.fetchone()
        if report:
            return {
                'id': report[0],
                'title': report[1],
                'content': report[2],
                'author': report[3],
                'created_at': report[4],
            }
        raise cherrypy.HTTPError(404, 'Report not found')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_report(self, **params):
        department = params.get('department')
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        query = self._build_report_query(department, start_date, end_date)

        with closing(_connect()) as conn:
            c = conn.cursor()
            c.execute(query)
            rows = c.fetchall()

        reports = [
            {
                'id': row[0],
                'title': row[1],
                'author': row[2],
                'department': row[3],
                'created_at': row[4],
            }
            for row in rows
        ]
        return {'reports': reports}

    @staticmethod
    def _build_report_query(department, start_date, end_date):
        # NOTE: values are interpolated directly into the SQL string, exactly
        # as in the original implementation (behaviour intentionally preserved).
        query = 'SELECT r.id, r.title, e.name as author, d.name as department, r.created_at '
        query += 'FROM reports r JOIN employees e ON r.created_by = e.id '
        query += 'JOIN departments d ON e.department_id = d.id '

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


if __name__ == '__main__':
    cherrypy.quickstart(
        ReportSystem(),
        '/',
        {
            '/': {
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'application/json')],
            }
        },
    )
