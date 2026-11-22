import cherrypy
import sqlite3
import json
from datetime import datetime, timedelta
import re

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

DB_PATH = 'library.db'
DATE_FORMAT = '%Y-%m-%d'
LOAN_PERIOD_DAYS = 14

SEARCH_FORBIDDEN_CHARS = re.compile(r"""[;'"\\]""")

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500

SERVER_CONFIG = {
    'server.socket_port': 8080,
    'environment': 'production',
    'tools.sessions.on': True,
    'tools.sessions.secure': True,
}

CREATE_BOOKS_TABLE = '''
            CREATE TABLE IF NOT EXISTS books (
                book_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT UNIQUE NOT NULL,
                published_date TEXT,
                genre TEXT,
                available_copies INTEGER DEFAULT 1
            )
        '''

CREATE_MEMBERS_TABLE = '''
            CREATE TABLE IF NOT EXISTS members (
                member_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                join_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        '''

CREATE_LOANS_TABLE = '''
            CREATE TABLE IF NOT EXISTS loans (
                loan_id INTEGER PRIMARY KEY,
                book_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                loan_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                return_date TEXT,
                FOREIGN KEY(book_id) REFERENCES books(book_id),
                FOREIGN KEY(member_id) REFERENCES members(member_id)
            )
        '''

SCHEMA_STATEMENTS = (CREATE_BOOKS_TABLE, CREATE_MEMBERS_TABLE, CREATE_LOANS_TABLE)

COUNT_BOOKS = 'SELECT COUNT(*) FROM books'

INSERT_BOOK = '''
                INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
                VALUES (?, ?, ?, ?, ?, ?)
            '''

INSERT_MEMBER = '''
                INSERT INTO members (name, email)
                VALUES (?, ?)
            '''

SEED_BOOKS = [
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
]

SEED_MEMBERS = [
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
]

SELECT_BOOK_AVAILABILITY = 'SELECT available_copies FROM books WHERE book_id = ?'
SELECT_MEMBER_EXISTS = 'SELECT 1 FROM members WHERE member_id = ?'

INSERT_LOAN = '''
                INSERT INTO loans (book_id, member_id, loan_date, due_date)
                VALUES (?, ?, ?, ?)
            '''

DECREMENT_COPIES = '''
                UPDATE books SET available_copies = available_copies - 1
                WHERE book_id = ?
            '''

INCREMENT_COPIES = '''
                UPDATE books SET available_copies = available_copies + 1
                WHERE book_id = ?
            '''

SELECT_OPEN_LOAN = 'SELECT book_id FROM loans WHERE loan_id = ? AND return_date IS NULL'

MARK_LOAN_RETURNED = '''
                UPDATE loans SET return_date = ?
                WHERE loan_id = ?
            '''

BOOK_FIELDS = (
    'book_id', 'title', 'author', 'isbn',
    'published_date', 'genre', 'available_copies',
)

SEARCH_BASE_QUERY = 'SELECT * FROM books WHERE 1=1'
SEARCH_LIKE_FILTERS = (
    ('title', ' AND title LIKE ?'),
    ('author', ' AND author LIKE ?'),
    ('genre', ' AND genre LIKE ?'),
)
SEARCH_AVAILABLE_CLAUSE = ' AND available_copies > 0'

# Error messages
MSG_INVALID_ID = 'Invalid ID format'
MSG_MISSING_PARAMS = 'Missing required parameters'
MSG_MISSING_LOAN_ID = 'Missing loan_id parameter'
MSG_BOOK_UNAVAILABLE = 'Book not available for borrowing'
MSG_MEMBER_NOT_FOUND = 'Member not found'
MSG_LOAN_NOT_FOUND = 'Loan not found or already returned'
MSG_INTERNAL = 'Internal server error'
MSG_BORROW_FAILED = 'Failed to process book loan'
MSG_RETURN_FAILED = 'Failed to process book return'


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _format_date(moment):
    return moment.strftime(DATE_FORMAT)


def _today():
    return _format_date(datetime.now())


def _due_date():
    return _format_date(datetime.now() + timedelta(days=LOAN_PERIOD_DAYS))


def _error_response(status, message):
    cherrypy.response.status = status
    return {'error': message}


def _row_to_book(row):
    return dict(zip(BOOK_FIELDS, row))


class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.init_db()

    # -- database setup ----------------------------------------------------

    def init_db(self):
        cursor = self.conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        cursor.execute(COUNT_BOOKS)
        if cursor.fetchone()[0] == 0:
            self._seed_data(cursor)
        self.conn.commit()

    @staticmethod
    def _seed_data(cursor):
        cursor.executemany(INSERT_BOOK, SEED_BOOKS)
        cursor.executemany(INSERT_MEMBER, SEED_MEMBERS)

    # -- validation --------------------------------------------------------

    def validate_id(self, id_str):
        if not id_str or not id_str.isdigit():
            raise ValueError(MSG_INVALID_ID)
        return int(id_str)

    def validate_search_input(self, input_str):
        if not input_str:
            return ''
        return SEARCH_FORBIDDEN_CHARS.sub('', input_str)

    # -- query builders / data access helpers ------------------------------

    @staticmethod
    def _build_search_query(filters, available_only):
        query = SEARCH_BASE_QUERY
        query_params = []
        for field, clause in SEARCH_LIKE_FILTERS:
            value = filters[field]
            if value:
                query += clause
                query_params.append(f'%{value}%')
        if available_only:
            query += SEARCH_AVAILABLE_CLAUSE
        return query, query_params

    @staticmethod
    def _ensure_book_available(cursor, book_id):
        cursor.execute(SELECT_BOOK_AVAILABILITY, (book_id,))
        result = cursor.fetchone()
        if not result or result[0] <= 0:
            raise ValueError(MSG_BOOK_UNAVAILABLE)

    @staticmethod
    def _ensure_member_exists(cursor, member_id):
        cursor.execute(SELECT_MEMBER_EXISTS, (member_id,))
        if not cursor.fetchone():
            raise ValueError(MSG_MEMBER_NOT_FOUND)

    @staticmethod
    def _find_open_loan_book(cursor, loan_id):
        cursor.execute(SELECT_OPEN_LOAN, (loan_id,))
        result = cursor.fetchone()
        if not result:
            raise ValueError(MSG_LOAN_NOT_FOUND)
        return result[0]

    # -- routes ------------------------------------------------------------

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        try:
            filters = {
                field: self.validate_search_input(params.get(field, ''))
                for field, _ in SEARCH_LIKE_FILTERS
            }
            available_only = params.get('available_only', 'false').lower() == 'true'
            query, query_params = self._build_search_query(filters, available_only)
            cursor = self.conn.cursor()
            cursor.execute(query, query_params)
            books = [_row_to_book(row) for row in cursor.fetchall()]
            return {'books': books}
        except Exception:
            return _error_response(HTTP_INTERNAL_ERROR, MSG_INTERNAL)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            if not all((key in params for key in ['book_id', 'member_id'])):
                raise ValueError(MSG_MISSING_PARAMS)
            book_id = self.validate_id(params['book_id'])
            member_id = self.validate_id(params['member_id'])
            loan_date = _today()
            due_date = _due_date()
            cursor = self.conn.cursor()
            self._ensure_book_available(cursor, book_id)
            self._ensure_member_exists(cursor, member_id)
            cursor.execute(INSERT_LOAN, (book_id, member_id, loan_date, due_date))
            cursor.execute(DECREMENT_COPIES, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except ValueError as e:
            return _error_response(HTTP_BAD_REQUEST, str(e))
        except Exception:
            self.conn.rollback()
            return _error_response(HTTP_INTERNAL_ERROR, MSG_BORROW_FAILED)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            if 'loan_id' not in params:
                raise ValueError(MSG_MISSING_LOAN_ID)
            loan_id = self.validate_id(params['loan_id'])
            return_date = _today()
            cursor = self.conn.cursor()
            book_id = self._find_open_loan_book(cursor, loan_id)
            cursor.execute(MARK_LOAN_RETURNED, (return_date, loan_id))
            cursor.execute(INCREMENT_COPIES, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except ValueError as e:
            return _error_response(HTTP_BAD_REQUEST, str(e))
        except Exception:
            self.conn.rollback()
            return _error_response(HTTP_INTERNAL_ERROR, MSG_RETURN_FAILED)


if __name__ == '__main__':
    cherrypy.config.update(SERVER_CONFIG)
    cherrypy.quickstart(LibrarySystem())
