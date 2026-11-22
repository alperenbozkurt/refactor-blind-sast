import cherrypy
import sqlite3
import json
from datetime import datetime

_DATABASE_PATH = 'reports.db'


class ReportSystem:
    """CherryPy application for creating and querying employee reports."""

    def __init__(self):
        self.init_db()

    def init_db(self):
        """Create the database tables and seed them with sample data."""
        conn = sqlite3.connect(_DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments
                (id INTEGER PRIMARY KEY,
                 name TEXT NOT NULL)
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees
                (id INTEGER PRIMARY KEY,
                 name TEXT NOT NULL,
                 department_id INTEGER,
                 salary REAL,
                 FOREIGN KEY(department_id) REFERENCES departments(id))
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports
                (id INTEGER PRIMARY KEY,
                 title TEXT NOT NULL,
                 content TEXT,
                 created_by INTEGER,
                 created_at DATETIME,
                 FOREIGN KEY(created_by) REFERENCES employees(id))
        ''')

        cursor.execute('SELECT COUNT(*) FROM departments')
        if cursor.fetchone()[0] == 0:
            departments = [
                (1, 'HR'),
                (2, 'Engineering'),
                (3, 'Finance'),
            ]
            cursor.executemany(
                'INSERT INTO departments VALUES (?, ?)', departments)

            employees = [
                (1, 'Alice Smith', 1, 65000),
                (2, 'Bob Johnson', 2, 85000),
                (3, 'Carol Williams', 3, 75000),
            ]
            cursor.executemany(
                'INSERT INTO employees VALUES (?, ?, ?, ?)', employees)

            reports = [
                (1, 'Q1 Hiring Report', 'Hired 5 new engineers', 1,
                 '2023-01-15'),
                (2, 'System Upgrade', 'Updated all servers', 2,
                 '2023-02-20'),
            ]
            cursor.executemany(
                'INSERT INTO reports VALUES (?, ?, ?, ?, ?)', reports)

            conn.commit()
        conn.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        """Insert a new report and return its generated id."""
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])

            conn = sqlite3.connect(_DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO reports (title, content, created_by, created_at)'
                ' VALUES (?, ?, ?, ?)',
                (title, content, created_by, datetime.now()))
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
        conn = sqlite3.connect(_DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT r.id, r.title, r.content, e.name as author, r.created_at'
            ' FROM reports r JOIN employees e ON r.created_by = e.id'
            ' WHERE r.id = ?',
            (report_id,))
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
        """Return reports filtered by department and/or creation date range."""
        department = params.get('department')
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        conn = sqlite3.connect(_DATABASE_PATH)
        cursor = conn.cursor()

        query = (
            'SELECT r.id, r.title, e.name as author, d.name as department, '
            'r.created_at '
            'FROM reports r JOIN employees e ON r.created_by = e.id '
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

        cursor.execute(query)
        reports = [
            {
                'id': row[0],
                'title': row[1],
                'author': row[2],
                'department': row[3],
                'created_at': row[4],
            }
            for row in cursor.fetchall()
        ]
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
