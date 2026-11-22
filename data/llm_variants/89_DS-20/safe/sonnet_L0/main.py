import cherrypy
import sqlite3
import json
from contextlib import closing
from datetime import datetime

DB_PATH = 'reports.db'

CREATE_TABLE_STATEMENTS = (
    'CREATE TABLE IF NOT EXISTS departments\n'
    '                     (id INTEGER PRIMARY KEY,\n'
    '                     name TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS employees\n'
    '                     (id INTEGER PRIMARY KEY,\n'
    '                     name TEXT NOT NULL,\n'
    '                     department_id INTEGER,\n'
    '                     salary REAL,\n'
    '                     FOREIGN KEY(department_id) REFERENCES departments(id))',
    'CREATE TABLE IF NOT EXISTS reports\n'
    '                     (id INTEGER PRIMARY KEY,\n'
    '                     title TEXT NOT NULL,\n'
    '                     content TEXT,\n'
    '                     created_by INTEGER,\n'
    '                     created_at DATETIME,\n'
    '                     FOREIGN KEY(created_by) REFERENCES employees(id))',
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

INSERT_REPORT_SQL = (
    'INSERT INTO reports (title, content, created_by, created_at) '
    'VALUES (?, ?, ?, ?)'
)

GET_REPORT_SQL = (
    'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
    'FROM reports r JOIN employees e ON r.created_by = e.id WHERE r.id = ?'
)

GENERATE_REPORT_BASE_SQL = (
    'SELECT r.id, r.title, e.name as author, d.name as department, r.created_at \n'
    '                   FROM reports r \n'
    '                   JOIN employees e ON r.created_by = e.id \n'
    '                   JOIN departments d ON e.department_id = d.id '
)


class ReportSystem:

    def __init__(self):
        self.init_db()

    @staticmethod
    def _connect():
        return closing(sqlite3.connect(DB_PATH))

    def init_db(self):
        with self._connect() as conn:
            c = conn.cursor()
            for statement in CREATE_TABLE_STATEMENTS:
                c.execute(statement)
            c.execute('SELECT COUNT(*) FROM departments')
            if c.fetchone()[0] == 0:
                c.executemany('INSERT INTO departments VALUES (?, ?)', SEED_DEPARTMENTS)
                c.executemany('INSERT INTO employees VALUES (?, ?, ?, ?)', SEED_EMPLOYEES)
                c.executemany('INSERT INTO reports VALUES (?, ?, ?, ?, ?)', SEED_REPORTS)
                conn.commit()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(INSERT_REPORT_SQL, (title, content, created_by, datetime.now()))
                report_id = c.lastrowid
                conn.commit()
            return {'status': 'success', 'report_id': report_id}
        except Exception as e:
            raise cherrypy.HTTPError(400, str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_report(self, report_id):
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(GET_REPORT_SQL, (report_id,))
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

        query = GENERATE_REPORT_BASE_SQL
        if conditions:
            query += 'WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY r.created_at DESC'

        with self._connect() as conn:
            c = conn.cursor()
            c.execute(query, query_params)
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
