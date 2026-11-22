import cherrypy
import sqlite3
import json
from datetime import datetime

DATABASE_FILE = 'reports.db'

SCHEMA_STATEMENTS = (
    'CREATE TABLE IF NOT EXISTS departments ('
    'id INTEGER PRIMARY KEY, '
    'name TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS employees ('
    'id INTEGER PRIMARY KEY, '
    'name TEXT NOT NULL, '
    'department_id INTEGER, '
    'salary REAL, '
    'FOREIGN KEY(department_id) REFERENCES departments(id))',
    'CREATE TABLE IF NOT EXISTS reports ('
    'id INTEGER PRIMARY KEY, '
    'title TEXT NOT NULL, '
    'content TEXT, '
    'created_by INTEGER, '
    'created_at DATETIME, '
    'FOREIGN KEY(created_by) REFERENCES employees(id))',
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


class ReportSystem:

    def __init__(self):
        self.init_db()

    @staticmethod
    def _connect():
        return sqlite3.connect(DATABASE_FILE)

    def init_db(self):
        conn = self._connect()
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        cursor.execute('SELECT COUNT(*) FROM departments')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                'INSERT INTO departments VALUES (?, ?)', SEED_DEPARTMENTS)
            cursor.executemany(
                'INSERT INTO employees VALUES (?, ?, ?, ?)', SEED_EMPLOYEES)
            cursor.executemany(
                'INSERT INTO reports VALUES (?, ?, ?, ?, ?)', SEED_REPORTS)
            conn.commit()
        conn.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO reports (title, content, created_by, created_at) '
                'VALUES (?, ?, ?, ?)',
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
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
            'FROM reports r '
            'JOIN employees e ON r.created_by = e.id '
            'WHERE r.id = ?',
            (report_id,),
        )
        report = cursor.fetchone()
        conn.close()
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
        if department:
            conditions.append(f"d.name = '{department}'")
        if start_date:
            conditions.append(f"r.created_at >= '{start_date}'")
        if end_date:
            conditions.append(f"r.created_at <= '{end_date}'")

        query = (
            'SELECT r.id, r.title, e.name as author, d.name as department, '
            'r.created_at '
            'FROM reports r '
            'JOIN employees e ON r.created_by = e.id '
            'JOIN departments d ON e.department_id = d.id '
        )
        if conditions:
            query += 'WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY r.created_at DESC'

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(query)
        columns = ('id', 'title', 'author', 'department', 'created_at')
        reports = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return {'reports': reports}


if __name__ == '__main__':
    config = {
        '/': {
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [
                ('Content-Type', 'application/json'),
            ],
        },
    }
    cherrypy.quickstart(ReportSystem(), '/', config)
