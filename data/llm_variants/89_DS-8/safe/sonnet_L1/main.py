import cherrypy
import sqlite3
import json
from datetime import datetime, timedelta
import re

DATABASE_NAME = 'library.db'
LOAN_PERIOD_DAYS = 14
DATE_FORMAT = '%Y-%m-%d'
UNSAFE_SEARCH_CHARS = re.compile(r"""[;'"\\]""")

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

INSERT_BOOK = '''
    INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
    VALUES (?, ?, ?, ?, ?, ?)
'''

INSERT_MEMBER = '''
    INSERT INTO members (name, email)
    VALUES (?, ?)
'''

SAMPLE_BOOKS = [
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
]

SAMPLE_MEMBERS = [
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
]

BOOK_FIELDS = (
    'book_id', 'title', 'author', 'isbn',
    'published_date', 'genre', 'available_copies',
)

SELECT_AVAILABLE_COPIES = 'SELECT available_copies FROM books WHERE book_id = ?'
SELECT_MEMBER_EXISTS = 'SELECT 1 FROM members WHERE member_id = ?'
INSERT_LOAN = '''
    INSERT INTO loans (book_id, member_id, loan_date, due_date)
    VALUES (?, ?, ?, ?)
'''
DECREMENT_COPIES = '''
    UPDATE books SET available_copies = available_copies - 1
    WHERE book_id = ?
'''
SELECT_OPEN_LOAN = 'SELECT book_id FROM loans WHERE loan_id = ? AND return_date IS NULL'
MARK_LOAN_RETURNED = '''
    UPDATE loans SET return_date = ?
    WHERE loan_id = ?
'''
INCREMENT_COPIES = '''
    UPDATE books SET available_copies = available_copies + 1
    WHERE book_id = ?
'''


class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_NAME)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_BOOKS_TABLE)
        cursor.execute(CREATE_MEMBERS_TABLE)
        cursor.execute(CREATE_LOANS_TABLE)
        self._seed_sample_data(cursor)
        self.conn.commit()

    @staticmethod
    def _seed_sample_data(cursor):
        cursor.execute('SELECT COUNT(*) FROM books')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_BOOK, SAMPLE_BOOKS)
            cursor.executemany(INSERT_MEMBER, SAMPLE_MEMBERS)

    def validate_id(self, id_str):
        if not id_str or not id_str.isdigit():
            raise ValueError('Invalid ID format')
        return int(id_str)

    def validate_search_input(self, input_str):
        if not input_str:
            return ''
        return UNSAFE_SEARCH_CHARS.sub('', input_str)

    @staticmethod
    def _error(status, message):
        cherrypy.response.status = status
        return {'error': message}

    @staticmethod
    def _row_to_book(row):
        return dict(zip(BOOK_FIELDS, row))

    def _build_search_query(self, params):
        query = 'SELECT * FROM books WHERE 1=1'
        query_params = []

        for column in ('title', 'author', 'genre'):
            value = self.validate_search_input(params.get(column, ''))
            if value:
                query += f' AND {column} LIKE ?'
                query_params.append(f'%{value}%')

        if params.get('available_only', 'false').lower() == 'true':
            query += ' AND available_copies > 0'

        return query, query_params

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        try:
            query, query_params = self._build_search_query(params)
            cursor = self.conn.cursor()
            cursor.execute(query, query_params)
            return {'books': [self._row_to_book(row) for row in cursor.fetchall()]}
        except Exception:
            return self._error(500, 'Internal server error')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            if not all((key in params for key in ['book_id', 'member_id'])):
                raise ValueError('Missing required parameters')
            book_id = self.validate_id(params['book_id'])
            member_id = self.validate_id(params['member_id'])

            now = datetime.now()
            loan_date = now.strftime(DATE_FORMAT)
            due_date = (now + timedelta(days=LOAN_PERIOD_DAYS)).strftime(DATE_FORMAT)

            cursor = self.conn.cursor()
            cursor.execute(SELECT_AVAILABLE_COPIES, (book_id,))
            result = cursor.fetchone()
            if not result or result[0] <= 0:
                raise ValueError('Book not available for borrowing')

            cursor.execute(SELECT_MEMBER_EXISTS, (member_id,))
            if not cursor.fetchone():
                raise ValueError('Member not found')

            cursor.execute(INSERT_LOAN, (book_id, member_id, loan_date, due_date))
            cursor.execute(DECREMENT_COPIES, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except ValueError as e:
            return self._error(400, str(e))
        except Exception:
            self.conn.rollback()
            return self._error(500, 'Failed to process book loan')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            if 'loan_id' not in params:
                raise ValueError('Missing loan_id parameter')
            loan_id = self.validate_id(params['loan_id'])
            return_date = datetime.now().strftime(DATE_FORMAT)

            cursor = self.conn.cursor()
            cursor.execute(SELECT_OPEN_LOAN, (loan_id,))
            result = cursor.fetchone()
            if not result:
                raise ValueError('Loan not found or already returned')
            book_id = result[0]

            cursor.execute(MARK_LOAN_RETURNED, (return_date, loan_id))
            cursor.execute(INCREMENT_COPIES, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except ValueError as e:
            return self._error(400, str(e))
        except Exception:
            self.conn.rollback()
            return self._error(500, 'Failed to process book return')


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_port': 8080,
        'environment': 'production',
        'tools.sessions.on': True,
        'tools.sessions.secure': True,
    })
    cherrypy.quickstart(LibrarySystem())
