import cherrypy
import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = 'reports.db'
APP_MOUNT_POINT = '/'

APP_CONFIG = {
    '/': {
        'tools.response_headers.on': True,
        'tools.response_headers.headers': [('Content-Type', 'application/json')],
    }
}

# --- Schema -----------------------------------------------------------------

CREATE_DEPARTMENTS_SQL = (
    'CREATE TABLE IF NOT EXISTS departments '
    '(id INTEGER PRIMARY KEY, '
    'name TEXT NOT NULL)'
)
CREATE_EMPLOYEES_SQL = (
    'CREATE TABLE IF NOT EXISTS employees '
    '(id INTEGER PRIMARY KEY, '
    'name TEXT NOT NULL, '
    'department_id INTEGER, '
    'salary REAL, '
    'FOREIGN KEY(department_id) REFERENCES departments(id))'
)
CREATE_REPORTS_SQL = (
    'CREATE TABLE IF NOT EXISTS reports '
    '(id INTEGER PRIMARY KEY, '
    'title TEXT NOT NULL, '
    'content TEXT, '
    'created_by INTEGER, '
    'created_at DATETIME, '
    'FOREIGN KEY(created_by) REFERENCES employees(id))'
)
SCHEMA_STATEMENTS = (CREATE_DEPARTMENTS_SQL, CREATE_EMPLOYEES_SQL, CREATE_REPORTS_SQL)

# --- Seed data --------------------------------------------------------------

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

# --- Queries ----------------------------------------------------------------

INSERT_REPORT_SQL = (
    'INSERT INTO reports (title, content, created_by, created_at) '
    'VALUES (?, ?, ?, ?)'
)
SELECT_REPORT_SQL = (
    'SELECT r.id, r.title, r.content, e.name as author, r.created_at '
    'FROM reports r JOIN employees e ON r.created_by = e.id WHERE r.id = ?'
)
GENERATE_REPORT_BASE_SQL = (
    'SELECT r.id, r.title, e.name as author, d.name as department, r.created_at '
    'FROM reports r JOIN employees e ON r.created_by = e.id '
    'JOIN departments d ON e.department_id = d.id '
)
GENERATE_REPORT_ORDER_SQL = ' ORDER BY r.created_at DESC'

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404


@contextmanager
def _connection(db_path=None):
    """Open a SQLite connection and guarantee it is closed afterwards."""
    conn = sqlite3.connect(db_path if db_path is not None else DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _report_detail_to_dict(row):
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


def _build_generate_query(department, start_date, end_date):
    """Build the filtered report query and its bound parameters.

    Values are passed as bound parameters rather than interpolated into the
    SQL text, which gives identical results for normal input while avoiding
    SQL injection.
    """
    conditions = []
    args = []
    if department:
        conditions.append('d.name = ?')
        args.append(department)
    if start_date:
        conditions.append('r.created_at >= ?')
        args.append(start_date)
    if end_date:
        conditions.append('r.created_at <= ?')
        args.append(end_date)

    query = GENERATE_REPORT_BASE_SQL
    if conditions:
        query += 'WHERE ' + ' AND '.join(conditions)
    query += GENERATE_REPORT_ORDER_SQL
    return query, tuple(args)


class ReportSystem:

    def __init__(self):
        self.init_db()

    def _create_schema(self, cursor):
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)

    def _seed_if_empty(self, conn, cursor):
        cursor.execute(COUNT_DEPARTMENTS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_DEPARTMENTS_SQL, SEED_DEPARTMENTS)
            cursor.executemany(INSERT_EMPLOYEES_SQL, SEED_EMPLOYEES)
            cursor.executemany(INSERT_REPORTS_SQL, SEED_REPORTS)
            conn.commit()

    def init_db(self):
        with _connection() as conn:
            c = conn.cursor()
            self._create_schema(c)
            self._seed_if_empty(conn, c)

    def _insert_report(self, title, content, created_by):
        with _connection() as conn:
            c = conn.cursor()
            c.execute(INSERT_REPORT_SQL, (title, content, created_by, datetime.now()))
            report_id = c.lastrowid
            conn.commit()
        return report_id

    def _fetch_report(self, report_id):
        with _connection() as conn:
            c = conn.cursor()
            c.execute(SELECT_REPORT_SQL, (report_id,))
            return c.fetchone()

    def _fetch_report_summaries(self, department, start_date, end_date):
        query, args = _build_generate_query(department, start_date, end_date)
        with _connection() as conn:
            c = conn.cursor()
            c.execute(query, args)
            return c.fetchall()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_report(self, **params):
        try:
            title = params['title']
            content = params['content']
            created_by = int(params['created_by'])
            report_id = self._insert_report(title, content, created_by)
            return {'status': 'success', 'report_id': report_id}
        except Exception as e:
            raise cherrypy.HTTPError(HTTP_BAD_REQUEST, str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_report(self, report_id):
        report = self._fetch_report(report_id)
        if report:
            return _report_detail_to_dict(report)
        raise cherrypy.HTTPError(HTTP_NOT_FOUND, 'Report not found')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_report(self, **params):
        department = params.get('department')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        rows = self._fetch_report_summaries(department, start_date, end_date)
        return {'reports': [_report_summary_to_dict(row) for row in rows]}


if __name__ == '__main__':
    cherrypy.quickstart(ReportSystem(), APP_MOUNT_POINT, APP_CONFIG)
