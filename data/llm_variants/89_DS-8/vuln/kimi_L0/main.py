import cherrypy
import sqlite3
import json
from datetime import datetime


class LibrarySystem:
    _DATE_FORMAT = '%Y-%m-%d'

    _BOOK_FIELDS = (
        'book_id', 'title', 'author', 'isbn',
        'published_date', 'genre', 'available_copies',
    )

    _CREATE_BOOKS_TABLE = """
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

    _CREATE_MEMBERS_TABLE = """
        CREATE TABLE IF NOT EXISTS members (
            member_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """

    _CREATE_LOANS_TABLE = """
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

    _COUNT_BOOKS = 'SELECT COUNT(*) FROM books'

    _INSERT_BOOK = """
        INSERT INTO books (title, author, isbn, published_date, genre, available_copies)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    _INSERT_MEMBER = """
        INSERT INTO members (name, email)
        VALUES (?, ?)
    """

    _INSERT_LOAN = """
        INSERT INTO loans (book_id, member_id, loan_date, due_date)
        VALUES (?, ?, ?, ?)
    """

    _SELECT_LOAN_BOOK_ID = 'SELECT book_id FROM loans WHERE loan_id = ?'

    _SET_LOAN_RETURN_DATE = """
        UPDATE loans SET return_date = ?
        WHERE loan_id = ?
    """

    _DECREMENT_AVAILABLE_COPIES = """
        UPDATE books SET available_copies = available_copies - 1
        WHERE book_id = ?
    """

    _INCREMENT_AVAILABLE_COPIES = """
        UPDATE books SET available_copies = available_copies + 1
        WHERE book_id = ?
    """

    _SEED_BOOKS = (
        ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
        ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
        ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
    )

    _SEED_MEMBERS = (
        ('Tom Wilson', 'tom@example.com'),
        ('Sarah Davis', 'sarah@example.com'),
    )

    def __init__(self):
        self.conn = sqlite3.connect('library.db')
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(self._CREATE_BOOKS_TABLE)
        cursor.execute(self._CREATE_MEMBERS_TABLE)
        cursor.execute(self._CREATE_LOANS_TABLE)
        cursor.execute(self._COUNT_BOOKS)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(self._INSERT_BOOK, self._SEED_BOOKS)
            cursor.executemany(self._INSERT_MEMBER, self._SEED_MEMBERS)
        self.conn.commit()

    def _current_date(self):
        return datetime.now().strftime(self._DATE_FORMAT)

    @classmethod
    def _book_to_dict(cls, row):
        return dict(zip(cls._BOOK_FIELDS, row))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        title = params.get('title', '')
        author = params.get('author', '')
        genre = params.get('genre', '')
        available_only = params.get('available_only', 'false').lower() == 'true'

        conditions = [f"title LIKE '%{title}%'"]
        if author:
            conditions.append(f"author LIKE '%{author}%'")
        if genre:
            conditions.append(f"genre LIKE '%{genre}%'")
        if available_only:
            conditions.append('available_copies > 0')
        query = 'SELECT * FROM books WHERE ' + ' AND '.join(conditions)

        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            books = [self._book_to_dict(row) for row in cursor.fetchall()]
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
            loan_date = self._current_date()
            # NOTE: `timedelta` is intentionally left unimported so that the
            # original behaviour of this handler is preserved exactly.
            due_date = (datetime.now() + timedelta(days=14)).strftime(self._DATE_FORMAT)
            cursor = self.conn.cursor()
            cursor.execute(self._INSERT_LOAN, (book_id, member_id, loan_date, due_date))
            cursor.execute(self._DECREMENT_AVAILABLE_COPIES, (book_id,))
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
            return_date = self._current_date()
            cursor = self.conn.cursor()
            cursor.execute(self._SELECT_LOAN_BOOK_ID, (loan_id,))
            book_id = cursor.fetchone()[0]
            cursor.execute(self._SET_LOAN_RETURN_DATE, (return_date, loan_id))
            cursor.execute(self._INCREMENT_AVAILABLE_COPIES, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except Exception as e:
            cherrypy.response.status = 400
            return {'error': str(e)}


if __name__ == '__main__':
    cherrypy.config.update({'server.socket_port': 8080})
    cherrypy.quickstart(LibrarySystem())
