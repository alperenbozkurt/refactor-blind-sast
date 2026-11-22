"""A simple library management web service built with CherryPy and SQLite.

Exposes JSON endpoints to search the book catalogue and to borrow and
return books. Running the module directly starts the server on port 8080.
"""

import cherrypy
import sqlite3
import json
from datetime import datetime, timedelta
import re

DATABASE_FILE = 'library.db'
DATE_FORMAT = '%Y-%m-%d'
LOAN_PERIOD_DAYS = 14

CREATE_BOOKS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS books (
        book_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        isbn TEXT UNIQUE NOT NULL,
        published_date TEXT,
        genre TEXT,
        available_copies INTEGER DEFAULT 1
    )
"""

CREATE_MEMBERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS members (
        member_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        join_date TEXT DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_LOANS_TABLE_SQL = """
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
"""

INSERT_BOOK_SQL = """
    INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
    VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_MEMBER_SQL = """
    INSERT INTO members (name, email)
    VALUES (?, ?)
"""

INSERT_LOAN_SQL = """
    INSERT INTO loans (book_id, member_id, loan_date, due_date)
    VALUES (?, ?, ?, ?)
"""

DECREMENT_AVAILABLE_COPIES_SQL = """
    UPDATE books SET available_copies = available_copies - 1
    WHERE book_id = ?
"""

INCREMENT_AVAILABLE_COPIES_SQL = """
    UPDATE books SET available_copies = available_copies + 1
    WHERE book_id = ?
"""

SET_RETURN_DATE_SQL = """
    UPDATE loans SET return_date = ?
    WHERE loan_id = ?
"""

SAMPLE_BOOKS = [
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
]

SAMPLE_MEMBERS = [
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
]

# Column order of rows returned by "SELECT * FROM books", used to build
# the JSON representation of a book.
BOOK_ROW_FIELDS = (
    'book_id', 'title', 'author', 'isbn', 'published_date', 'genre', 'available_copies',
)


class LibrarySystem:
    """CherryPy root object exposing the library's JSON API endpoints."""

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE)
        self.init_db()

    def init_db(self):
        """Create the schema if needed and seed sample data into an empty library."""
        cursor = self.conn.cursor()
        for create_table_sql in (
            CREATE_BOOKS_TABLE_SQL,
            CREATE_MEMBERS_TABLE_SQL,
            CREATE_LOANS_TABLE_SQL,
        ):
            cursor.execute(create_table_sql)

        cursor.execute('SELECT COUNT(*) FROM books')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_BOOK_SQL, SAMPLE_BOOKS)
            cursor.executemany(INSERT_MEMBER_SQL, SAMPLE_MEMBERS)
        self.conn.commit()

    def validate_id(self, id_str):
        """Return the integer value of id_str, rejecting non-numeric input."""
        if not id_str or not id_str.isdigit():
            raise ValueError('Invalid ID format')
        return int(id_str)

    def validate_search_input(self, input_str):
        """Strip characters commonly used for SQL injection from search input."""
        if not input_str:
            return ''
        return re.sub(r'[;\'"\\]', '', input_str)

    @staticmethod
    def _book_row_to_dict(row):
        """Map a row from the books table to its JSON representation."""
        return dict(zip(BOOK_ROW_FIELDS, row))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        """Search books by title, author and/or genre, optionally only available ones."""
        try:
            title = self.validate_search_input(params.get('title', ''))
            author = self.validate_search_input(params.get('author', ''))
            genre = self.validate_search_input(params.get('genre', ''))
            available_only = params.get('available_only', 'false').lower() == 'true'

            query = 'SELECT * FROM books WHERE 1=1'
            query_params = []
            if title:
                query += ' AND title LIKE ?'
                query_params.append(f'%{title}%')
            if author:
                query += ' AND author LIKE ?'
                query_params.append(f'%{author}%')
            if genre:
                query += ' AND genre LIKE ?'
                query_params.append(f'%{genre}%')
            if available_only:
                query += ' AND available_copies > 0'

            cursor = self.conn.cursor()
            cursor.execute(query, query_params)
            books = [self._book_row_to_dict(row) for row in cursor.fetchall()]
            return {'books': books}
        except Exception:
            cherrypy.response.status = 500
            return {'error': 'Internal server error'}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        """Lend a book to a member, creating a loan and decrementing its stock."""
        try:
            if not all(key in params for key in ('book_id', 'member_id')):
                raise ValueError('Missing required parameters')
            book_id = self.validate_id(params['book_id'])
            member_id = self.validate_id(params['member_id'])
            loan_date = datetime.now().strftime(DATE_FORMAT)
            due_date = (datetime.now() + timedelta(days=LOAN_PERIOD_DAYS)).strftime(DATE_FORMAT)

            cursor = self.conn.cursor()
            cursor.execute('SELECT available_copies FROM books WHERE book_id = ?', (book_id,))
            result = cursor.fetchone()
            if not result or result[0] <= 0:
                raise ValueError('Book not available for borrowing')

            cursor.execute('SELECT 1 FROM members WHERE member_id = ?', (member_id,))
            if not cursor.fetchone():
                raise ValueError('Member not found')

            cursor.execute(INSERT_LOAN_SQL, (book_id, member_id, loan_date, due_date))
            cursor.execute(DECREMENT_AVAILABLE_COPIES_SQL, (book_id,))
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
        """Mark an open loan as returned and increment the book's stock."""
        try:
            if 'loan_id' not in params:
                raise ValueError('Missing loan_id parameter')
            loan_id = self.validate_id(params['loan_id'])
            return_date = datetime.now().strftime(DATE_FORMAT)

            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT book_id FROM loans WHERE loan_id = ? AND return_date IS NULL',
                (loan_id,),
            )
            result = cursor.fetchone()
            if not result:
                raise ValueError('Loan not found or already returned')
            book_id = result[0]

            cursor.execute(SET_RETURN_DATE_SQL, (return_date, loan_id))
            cursor.execute(INCREMENT_AVAILABLE_COPIES_SQL, (book_id,))
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
