import cherrypy
import sqlite3
import json
from datetime import datetime, timedelta
import re

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

_INSERT_BOOK_SQL = '''
    INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
    VALUES (?, ?, ?, ?, ?, ?)
'''

_INSERT_MEMBER_SQL = '''
    INSERT INTO members (name, email)
    VALUES (?, ?)
'''

_SAMPLE_BOOKS = [
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
]

_SAMPLE_MEMBERS = [
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
]

_BOOK_FIELDS = (
    'book_id', 'title', 'author', 'isbn',
    'published_date', 'genre', 'available_copies',
)

_INSERT_LOAN_SQL = '''
    INSERT INTO loans (book_id, member_id, loan_date, due_date)
    VALUES (?, ?, ?, ?)
'''

_DECREMENT_COPIES_SQL = '''
    UPDATE books SET available_copies = available_copies - 1
    WHERE book_id = ?
'''

_INCREMENT_COPIES_SQL = '''
    UPDATE books SET available_copies = available_copies + 1
    WHERE book_id = ?
'''

_MARK_RETURNED_SQL = '''
    UPDATE loans SET return_date = ?
    WHERE loan_id = ?
'''

_SEARCH_SANITIZE_PATTERN = '[;\\\'"\\\\]'
_DATE_FORMAT = '%Y-%m-%d'
_LOAN_PERIOD_DAYS = 14


class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect('library.db')
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        for statement in (_CREATE_BOOKS_SQL, _CREATE_MEMBERS_SQL, _CREATE_LOANS_SQL):
            cursor.execute(statement)
        cursor.execute('SELECT COUNT(*) FROM books')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(_INSERT_BOOK_SQL, _SAMPLE_BOOKS)
            cursor.executemany(_INSERT_MEMBER_SQL, _SAMPLE_MEMBERS)
        self.conn.commit()

    def validate_id(self, id_str):
        if not id_str or not id_str.isdigit():
            raise ValueError('Invalid ID format')
        return int(id_str)

    def validate_search_input(self, input_str):
        if not input_str:
            return ''
        return re.sub(_SEARCH_SANITIZE_PATTERN, '', input_str)

    @staticmethod
    def _book_row_to_dict(row):
        return dict(zip(_BOOK_FIELDS, row))

    @staticmethod
    def _today():
        return datetime.now().strftime(_DATE_FORMAT)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        try:
            title = self.validate_search_input(params.get('title', ''))
            author = self.validate_search_input(params.get('author', ''))
            genre = self.validate_search_input(params.get('genre', ''))
            available_only = params.get('available_only', 'false').lower() == 'true'

            query = 'SELECT * FROM books WHERE 1=1'
            query_params = []
            for column, value in (('title', title), ('author', author), ('genre', genre)):
                if value:
                    query += f' AND {column} LIKE ?'
                    query_params.append(f'%{value}%')
            if available_only:
                query += ' AND available_copies > 0'

            cursor = self.conn.cursor()
            cursor.execute(query, query_params)
            return {'books': [self._book_row_to_dict(row) for row in cursor.fetchall()]}
        except Exception:
            cherrypy.response.status = 500
            return {'error': 'Internal server error'}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            if not all(key in params for key in ('book_id', 'member_id')):
                raise ValueError('Missing required parameters')
            book_id = self.validate_id(params['book_id'])
            member_id = self.validate_id(params['member_id'])

            now = datetime.now()
            loan_date = now.strftime(_DATE_FORMAT)
            due_date = (now + timedelta(days=_LOAN_PERIOD_DAYS)).strftime(_DATE_FORMAT)

            cursor = self.conn.cursor()
            cursor.execute('SELECT available_copies FROM books WHERE book_id = ?', (book_id,))
            result = cursor.fetchone()
            if not result or result[0] <= 0:
                raise ValueError('Book not available for borrowing')

            cursor.execute('SELECT 1 FROM members WHERE member_id = ?', (member_id,))
            if not cursor.fetchone():
                raise ValueError('Member not found')

            cursor.execute(_INSERT_LOAN_SQL, (book_id, member_id, loan_date, due_date))
            cursor.execute(_DECREMENT_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except ValueError as e:
            cherrypy.response.status = 400
            return {'error': str(e)}
        except Exception:
            self.conn.rollback()
            cherrypy.response.status = 500
            return {'error': 'Failed to process book loan'}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            if 'loan_id' not in params:
                raise ValueError('Missing loan_id parameter')
            loan_id = self.validate_id(params['loan_id'])
            return_date = self._today()

            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT book_id FROM loans WHERE loan_id = ? AND return_date IS NULL',
                (loan_id,),
            )
            result = cursor.fetchone()
            if not result:
                raise ValueError('Loan not found or already returned')
            book_id = result[0]

            cursor.execute(_MARK_RETURNED_SQL, (return_date, loan_id))
            cursor.execute(_INCREMENT_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except ValueError as e:
            cherrypy.response.status = 400
            return {'error': str(e)}
        except Exception:
            self.conn.rollback()
            cherrypy.response.status = 500
            return {'error': 'Failed to process book return'}


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_port': 8080,
        'environment': 'production',
        'tools.sessions.on': True,
        'tools.sessions.secure': True,
    })
    cherrypy.quickstart(LibrarySystem())
