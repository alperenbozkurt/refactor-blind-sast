import cherrypy
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime

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
SCHEMA_STATEMENTS = (
    CREATE_DEPARTMENTS_SQL,
    CREATE_EMPLOYEES_SQL,
    CREATE_REPORTS_SQL,
)

COUNT_DEPARTMENTS_SQL = 'SELECT COUNT(*) FROM departments'
INSERT_DEPARTMENTS_SQL = 'INSERT INTO departments VALUES (?, ?)'
INSERT_EMPLOYEES_SQL = 'INSERT INTO employees VALUES (?, ?, ?, ?)'
INSERT_REPORTS_SQL = 'INSERT INTO reports VALUES (?, ?, ?, ?, ?)'

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
SELECT_REPORT_SQL = (
    'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
    'FROM reports r JOIN employees e ON r.created_by = e.id WHERE r.id = ?'
)
GENERATE_REPORT_BASE_SQL = (
    'SELECT r.id, r.title, e.name as author, d.name as department, r.created_at \n'
    '                   FROM reports r \n'
    '                   JOIN employees e ON r.created_by = e.id \n'
    '                   JOIN departments d ON e.department_id = d.id '
)
GENERATE_REPORT_ORDER_SQL = ' ORDER BY r.created_at DESC'

FILTER_DEPARTMENT = 'd.name = ?'
FILTER_START_DATE = 'r.created_at >= ?'
FILTER_END_DATE = 'r.created_at <= ?'

SERVER_MOUNT_POINT = '/'
SERVER_CONFIG = {
    '/': {
        'tools.response_headers.on': True,
        'tools.response_headers.headers': [('Content-Type', 'application/json')],
    }
}


@contextmanager
def _db_connection():
    """Open a connection to the reports database and always close it."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _create_schema(cursor):
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)


def _seed_database(cursor):
    cursor.executemany(INSERT_DEPARTMENTS_SQL, SEED_DEPARTMENTS)
    cursor.executemany(INSERT_EMPLOYEES_SQL, SEED_EMPLOYEES)
    cursor.executemany(INSERT_REPORTS_SQL, SEED_REPORTS)


def _is_empty(cursor):
    cursor.execute(COUNT_DEPARTMENTS_SQL)
    return cursor.fetchone()[0] == 0


def _report_to_dict(row):
    return {
        'id': row[0],
        'title': row[1],
        'content': row[2],
        'author': row[3],
        'created_at': row[4],
    }


def _report_summary_to_dict(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'department': row[3],
        'created_at': row[4],
    }


def _build_report_query(department, start_date, end_date):
    """Build the filtered report query and its parameters."""
    conditions = []
    query_params = []
    if department:
        conditions.append(FILTER_DEPARTMENT)
        query_params.append(department)
    if start_date:
        conditions.append(FILTER_START_DATE)
        query_params.append(start_date)
    if end_date:
        conditions.append(FILTER_END_DATE)
        query_params.append(end_date)

    query = GENERATE_REPORT_BASE_SQL
    if conditions:
        query += 'WHERE ' + ' AND '.join(conditions)
    query += GENERATE_REPORT_ORDER_SQL
    return query, query_params


class ReportSystem:

    def __init__(self):
        self.init_db()

    def init_db(self):
        with _db_connection() as conn:
            c = conn.cursor()
            _create_schema(c)
            if _is_empty(c):
                _seed_database(c)
                conn.commit()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])
            with _db_connection() as conn:
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
        with _db_connection() as conn:
            c = conn.cursor()
            c.execute(SELECT_REPORT_SQL, (report_id,))
            report = c.fetchone()
        if report:
            return _report_to_dict(report)
        raise cherrypy.HTTPError(404, 'Report not found')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_report(self, **params):
        department = params.get('department')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        query, query_params = _build_report_query(department, start_date, end_date)
        with _db_connection() as conn:
            c = conn.cursor()
            c.execute(query, query_params)
            reports = [_report_summary_to_dict(row) for row in c.fetchall()]
        return {'reports': reports}


if __name__ == '__main__':
    cherrypy.quickstart(ReportSystem(), SERVER_MOUNT_POINT, SERVER_CONFIG)
