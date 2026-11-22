import cherrypy
import sqlite3
import json
from datetime import datetime

# Note: `timedelta` is intentionally not imported, to preserve the original
# behaviour of borrow_book (the resulting NameError is reported as a 400 error).

DB_PATH = 'library.db'
DATE_FORMAT = '%Y-%m-%d'

CREATE_BOOKS_SQL = '''
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

CREATE_MEMBERS_SQL = '''
    CREATE TABLE IF NOT EXISTS members (
        member_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        join_date TEXT DEFAULT CURRENT_TIMESTAMP
    )
'''

CREATE_LOANS_SQL = '''
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

INSERT_BOOK_SQL = '''
    INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
    VALUES (?, ?, ?, ?, ?, ?)
'''

INSERT_MEMBER_SQL = '''
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

INSERT_LOAN_SQL = '''
    INSERT INTO loans (book_id, member_id, loan_date, due_date)
    VALUES (?, ?, ?, ?)
'''

DECREMENT_COPIES_SQL = '''
    UPDATE books SET available_copies = available_copies - 1
    WHERE book_id = ?
'''

INCREMENT_COPIES_SQL = '''
    UPDATE books SET available_copies = available_copies + 1
    WHERE book_id = ?
'''

SET_RETURN_DATE_SQL = '''
    UPDATE loans SET return_date = ?
    WHERE loan_id = ?
'''

BOOK_FIELDS = ('book_id', 'title', 'author', 'isbn', 'published_date', 'genre', 'available_copies')


def _today():
    return datetime.now().strftime(DATE_FORMAT)


def _book_row_to_dict(row):
    return dict(zip(BOOK_FIELDS, row[:len(BOOK_FIELDS)]))


def _error(status, exc):
    cherrypy.response.status = status
    return {'error': str(exc)}


class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        for statement in (CREATE_BOOKS_SQL, CREATE_MEMBERS_SQL, CREATE_LOANS_SQL):
            cursor.execute(statement)
        cursor.execute('SELECT COUNT(*) FROM books')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_BOOK_SQL, SAMPLE_BOOKS)
            cursor.executemany(INSERT_MEMBER_SQL, SAMPLE_MEMBERS)
        self.conn.commit()

    @staticmethod
    def _build_search_query(title, author, genre, available_only):
        query = f"SELECT * FROM books WHERE title LIKE '%{title}%'"
        if author:
            query += f" AND author LIKE '%{author}%'"
        if genre:
            query += f" AND genre LIKE '%{genre}%'"
        if available_only:
            query += ' AND available_copies > 0'
        return query

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        title = params.get('title', '')
        author = params.get('author', '')
        genre = params.get('genre', '')
        available_only = params.get('available_only', 'false').lower() == 'true'
        query = self._build_search_query(title, author, genre, available_only)
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            books = [_book_row_to_dict(row) for row in cursor.fetchall()]
            return {'books': books}
        except Exception as e:
            return _error(500, e)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            book_id = params['book_id']
            member_id = params['member_id']
            loan_date = _today()
            due_date = (datetime.now() + timedelta(days=14)).strftime(DATE_FORMAT)
            cursor = self.conn.cursor()
            cursor.execute(INSERT_LOAN_SQL, (book_id, member_id, loan_date, due_date))
            cursor.execute(DECREMENT_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except Exception as e:
            return _error(400, e)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            loan_id = params['loan_id']
            return_date = _today()
            cursor = self.conn.cursor()
            cursor.execute('SELECT book_id FROM loans WHERE loan_id = ?', (loan_id,))
            book_id = cursor.fetchone()[0]
            cursor.execute(SET_RETURN_DATE_SQL, (return_date, loan_id))
            cursor.execute(INCREMENT_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except Exception as e:
            return _error(400, e)


if __name__ == '__main__':
    cherrypy.config.update({'server.socket_port': 8080})
    cherrypy.quickstart(LibrarySystem())
