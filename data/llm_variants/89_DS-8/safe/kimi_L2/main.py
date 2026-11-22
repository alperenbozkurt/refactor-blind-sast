import cherrypy
import sqlite3
import json
from datetime import datetime, timedelta
import re


DATABASE_PATH = 'library.db'
DATE_FORMAT = '%Y-%m-%d'
LOAN_PERIOD_DAYS = 14

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

ERROR_INVALID_ID = 'Invalid ID format'
ERROR_INTERNAL_SERVER = 'Internal server error'
ERROR_LOAN_FAILED = 'Failed to process book loan'
ERROR_RETURN_FAILED = 'Failed to process book return'
ERROR_MISSING_REQUIRED_PARAMS = 'Missing required parameters'
ERROR_MISSING_LOAN_ID = 'Missing loan_id parameter'
ERROR_BOOK_UNAVAILABLE = 'Book not available for borrowing'
ERROR_MEMBER_NOT_FOUND = 'Member not found'
ERROR_LOAN_NOT_FOUND = 'Loan not found or already returned'

SERVER_CONFIG = {
    'server.socket_port': 8080,
    'environment': 'production',
    'tools.sessions.on': True,
    'tools.sessions.secure': True,
}

_CREATE_BOOKS_SQL = '''
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

_CREATE_MEMBERS_SQL = '''
            CREATE TABLE IF NOT EXISTS members (
                member_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                join_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        '''

_CREATE_LOANS_SQL = '''
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

_CREATE_TABLE_STATEMENTS = (
    _CREATE_BOOKS_SQL,
    _CREATE_MEMBERS_SQL,
    _CREATE_LOANS_SQL,
)

_COUNT_BOOKS_SQL = 'SELECT COUNT(*) FROM books'

_SEED_BOOKS_SQL = '''
                INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
                VALUES (?, ?, ?, ?, ?, ?)
            '''

_SEED_BOOKS = [
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
]

_SEED_MEMBERS_SQL = '''
                INSERT INTO members (name, email)
                VALUES (?, ?)
            '''

_SEED_MEMBERS = [
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
]

_SEARCH_INPUT_RE = re.compile("[;'\"\\\\]")

_BOOK_SEARCH_BASE_SQL = 'SELECT * FROM books WHERE 1=1'
_BOOK_SEARCH_TITLE_SQL = ' AND title LIKE ?'
_BOOK_SEARCH_AUTHOR_SQL = ' AND author LIKE ?'
_BOOK_SEARCH_GENRE_SQL = ' AND genre LIKE ?'
_BOOK_SEARCH_AVAILABLE_SQL = ' AND available_copies > 0'

_BORROW_REQUIRED_PARAMS = ('book_id', 'member_id')
_SELECT_AVAILABLE_COPIES_SQL = 'SELECT available_copies FROM books WHERE book_id = ?'
_SELECT_MEMBER_EXISTS_SQL = 'SELECT 1 FROM members WHERE member_id = ?'
_INSERT_LOAN_SQL = '''
                INSERT INTO loans (book_id, member_id, loan_date, due_date)
                VALUES (?, ?, ?, ?)
            '''
_DECREMENT_AVAILABLE_COPIES_SQL = '''
                UPDATE books SET available_copies = available_copies - 1
                WHERE book_id = ?
            '''

_SELECT_ACTIVE_LOAN_SQL = 'SELECT book_id FROM loans WHERE loan_id = ? AND return_date IS NULL'
_MARK_LOAN_RETURNED_SQL = '''
                UPDATE loans SET return_date = ?
                WHERE loan_id = ?
            '''
_INCREMENT_AVAILABLE_COPIES_SQL = '''
                UPDATE books SET available_copies = available_copies + 1
                WHERE book_id = ?
            '''


def _current_date():
    return datetime.now().strftime(DATE_FORMAT)


def _loan_due_date():
    return (datetime.now() + timedelta(days=LOAN_PERIOD_DAYS)).strftime(DATE_FORMAT)


def _book_from_row(row):
    return {
        'book_id': row[0],
        'title': row[1],
        'author': row[2],
        'isbn': row[3],
        'published_date': row[4],
        'genre': row[5],
        'available_copies': row[6],
    }


class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        for statement in _CREATE_TABLE_STATEMENTS:
            cursor.execute(statement)
        cursor.execute(_COUNT_BOOKS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(_SEED_BOOKS_SQL, _SEED_BOOKS)
            cursor.executemany(_SEED_MEMBERS_SQL, _SEED_MEMBERS)
        self.conn.commit()

    def validate_id(self, id_str):
        if not id_str or not id_str.isdigit():
            raise ValueError(ERROR_INVALID_ID)
        return int(id_str)

    def validate_search_input(self, input_str):
        if not input_str:
            return ''
        return _SEARCH_INPUT_RE.sub('', input_str)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        try:
            title = self.validate_search_input(params.get('title', ''))
            author = self.validate_search_input(params.get('author', ''))
            genre = self.validate_search_input(params.get('genre', ''))
            available_only = params.get('available_only', 'false').lower() == 'true'
            query = _BOOK_SEARCH_BASE_SQL
            query_params = []
            if title:
                query += _BOOK_SEARCH_TITLE_SQL
                query_params.append(f'%{title}%')
            if author:
                query += _BOOK_SEARCH_AUTHOR_SQL
                query_params.append(f'%{author}%')
            if genre:
                query += _BOOK_SEARCH_GENRE_SQL
                query_params.append(f'%{genre}%')
            if available_only:
                query += _BOOK_SEARCH_AVAILABLE_SQL
            cursor = self.conn.cursor()
            cursor.execute(query, query_params)
            return {'books': [_book_from_row(row) for row in cursor.fetchall()]}
        except Exception:
            cherrypy.response.status = HTTP_INTERNAL_SERVER_ERROR
            return {'error': ERROR_INTERNAL_SERVER}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            if not all((key in params for key in _BORROW_REQUIRED_PARAMS)):
                raise ValueError(ERROR_MISSING_REQUIRED_PARAMS)
            book_id = self.validate_id(params['book_id'])
            member_id = self.validate_id(params['member_id'])
            loan_date = _current_date()
            due_date = _loan_due_date()
            cursor = self.conn.cursor()
            cursor.execute(_SELECT_AVAILABLE_COPIES_SQL, (book_id,))
            result = cursor.fetchone()
            if not result or result[0] <= 0:
                raise ValueError(ERROR_BOOK_UNAVAILABLE)
            cursor.execute(_SELECT_MEMBER_EXISTS_SQL, (member_id,))
            if not cursor.fetchone():
                raise ValueError(ERROR_MEMBER_NOT_FOUND)
            cursor.execute(_INSERT_LOAN_SQL, (book_id, member_id, loan_date, due_date))
            cursor.execute(_DECREMENT_AVAILABLE_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except ValueError as e:
            cherrypy.response.status = HTTP_BAD_REQUEST
            return {'error': str(e)}
        except Exception:
            self.conn.rollback()
            cherrypy.response.status = HTTP_INTERNAL_SERVER_ERROR
            return {'error': ERROR_LOAN_FAILED}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            if 'loan_id' not in params:
                raise ValueError(ERROR_MISSING_LOAN_ID)
            loan_id = self.validate_id(params['loan_id'])
            return_date = _current_date()
            cursor = self.conn.cursor()
            cursor.execute(_SELECT_ACTIVE_LOAN_SQL, (loan_id,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(ERROR_LOAN_NOT_FOUND)
            book_id = result[0]
            cursor.execute(_MARK_LOAN_RETURNED_SQL, (return_date, loan_id))
            cursor.execute(_INCREMENT_AVAILABLE_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except ValueError as e:
            cherrypy.response.status = HTTP_BAD_REQUEST
            return {'error': str(e)}
        except Exception:
            self.conn.rollback()
            cherrypy.response.status = HTTP_INTERNAL_SERVER_ERROR
            return {'error': ERROR_RETURN_FAILED}


if __name__ == '__main__':
    cherrypy.config.update(SERVER_CONFIG)
    cherrypy.quickstart(LibrarySystem())
