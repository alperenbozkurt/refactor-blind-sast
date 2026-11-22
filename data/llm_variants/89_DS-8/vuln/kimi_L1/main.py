import cherrypy
import sqlite3
import json
from datetime import datetime

DATABASE_PATH = 'library.db'
DATE_FORMAT = '%Y-%m-%d'
LOAN_PERIOD_DAYS = 14

BOOK_COLUMNS = (
    'book_id',
    'title',
    'author',
    'isbn',
    'published_date',
    'genre',
    'available_copies',
)

CREATE_BOOKS_TABLE = """
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

CREATE_MEMBERS_TABLE = """
    CREATE TABLE IF NOT EXISTS members (
        member_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        join_date TEXT DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_LOANS_TABLE = """
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

TABLE_DEFINITIONS = (
    CREATE_BOOKS_TABLE,
    CREATE_MEMBERS_TABLE,
    CREATE_LOANS_TABLE,
)

COUNT_BOOKS = 'SELECT COUNT(*) FROM books'

INSERT_BOOK = """
    INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
    VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_MEMBER = """
    INSERT INTO members (name, email)
    VALUES (?, ?)
"""

INSERT_LOAN = """
    INSERT INTO loans (book_id, member_id, loan_date, due_date)
    VALUES (?, ?, ?, ?)
"""

DECREMENT_AVAILABLE_COPIES = """
    UPDATE books SET available_copies = available_copies - 1
    WHERE book_id = ?
"""

INCREMENT_AVAILABLE_COPIES = """
    UPDATE books SET available_copies = available_copies + 1
    WHERE book_id = ?
"""

SET_LOAN_RETURN_DATE = """
    UPDATE loans SET return_date = ?
    WHERE loan_id = ?
"""

SELECT_LOAN_BOOK_ID = 'SELECT book_id FROM loans WHERE loan_id = ?'

SEED_BOOKS = (
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
)

SEED_MEMBERS = (
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
)


class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        for statement in TABLE_DEFINITIONS:
            cursor.execute(statement)
        cursor.execute(COUNT_BOOKS)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_BOOK, SEED_BOOKS)
            cursor.executemany(INSERT_MEMBER, SEED_MEMBERS)
        self.conn.commit()

    @staticmethod
    def _row_to_book(row):
        return dict(zip(BOOK_COLUMNS, row))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        title = params.get('title', '')
        author = params.get('author', '')
        genre = params.get('genre', '')
        available_only = params.get('available_only', 'false').lower() == 'true'

        query = f"SELECT * FROM books WHERE title LIKE '%{title}%'"
        if author:
            query += f" AND author LIKE '%{author}%'"
        if genre:
            query += f" AND genre LIKE '%{genre}%'"
        if available_only:
            query += ' AND available_copies > 0'

        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            books = [self._row_to_book(row) for row in cursor.fetchall()]
            return {'books': books}
        except Exception as e:
            cherrypy.response.status = 500
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            book_id = params['book_id']
            member_id = params['member_id']
            loan_date = datetime.now().strftime(DATE_FORMAT)
            # NOTE: `timedelta` is intentionally left unimported here to
            # preserve the module's existing behaviour exactly.
            due_date = (datetime.now() + timedelta(days=LOAN_PERIOD_DAYS)).strftime(DATE_FORMAT)
            cursor = self.conn.cursor()
            cursor.execute(INSERT_LOAN, (book_id, member_id, loan_date, due_date))
            cursor.execute(DECREMENT_AVAILABLE_COPIES, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except Exception as e:
            cherrypy.response.status = 400
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            loan_id = params['loan_id']
            return_date = datetime.now().strftime(DATE_FORMAT)
            cursor = self.conn.cursor()
            cursor.execute(SELECT_LOAN_BOOK_ID, (loan_id,))
            book_id = cursor.fetchone()[0]
            cursor.execute(SET_LOAN_RETURN_DATE, (return_date, loan_id))
            cursor.execute(INCREMENT_AVAILABLE_COPIES, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except Exception as e:
            cherrypy.response.status = 400
            return {'error': str(e)}


if __name__ == '__main__':
    cherrypy.config.update({'server.socket_port': 8080})
    cherrypy.quickstart(LibrarySystem())
