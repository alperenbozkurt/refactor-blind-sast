"""Library management web service (refactored).

The behaviour of this module is identical to the original implementation:
same database, schema and seed data, same routes, same JSON responses and
the same command-line entry point.
"""

import cherrypy
import sqlite3
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'library.db'

SERVER_CONFIG = {
    'server.socket_port': 8080,
}

DATE_FORMAT = '%Y-%m-%d'
LOAN_PERIOD_DAYS = 14

STATUS_BAD_REQUEST = 400
STATUS_INTERNAL_SERVER_ERROR = 500

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

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

CREATE_TABLE_STATEMENTS = (
    CREATE_BOOKS_TABLE_SQL,
    CREATE_MEMBERS_TABLE_SQL,
    CREATE_LOANS_TABLE_SQL,
)

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

COUNT_BOOKS_SQL = 'SELECT COUNT(*) FROM books'

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

SELECT_LOAN_BOOK_ID_SQL = 'SELECT book_id FROM loans WHERE loan_id = ?'

MARK_LOAN_RETURNED_SQL = """
UPDATE loans SET return_date = ?
WHERE loan_id = ?
"""

DECREMENT_AVAILABLE_COPIES_SQL = """
UPDATE books SET available_copies = available_copies - 1
WHERE book_id = ?
"""

INCREMENT_AVAILABLE_COPIES_SQL = """
UPDATE books SET available_copies = available_copies + 1
WHERE book_id = ?
"""

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_BOOKS = (
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
)

SEED_MEMBERS = (
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _current_date():
    """Return today's date formatted for storage in the database."""
    return datetime.now().strftime(DATE_FORMAT)


def _book_from_row(row):
    """Convert a ``books`` table row into its JSON representation."""
    return {
        'book_id': row[0],
        'title': row[1],
        'author': row[2],
        'isbn': row[3],
        'published_date': row[4],
        'genre': row[5],
        'available_copies': row[6],
    }


def _build_search_query(title, author, genre, available_only):
    """Build the book search SQL exactly as the original implementation did."""
    query = f"SELECT * FROM books WHERE title LIKE '%{title}%'"
    if author:
        query += f" AND author LIKE '%{author}%'"
    if genre:
        query += f" AND genre LIKE '%{genre}%'"
    if available_only:
        query += ' AND available_copies > 0'
    return query


# ---------------------------------------------------------------------------
# Web application
# ---------------------------------------------------------------------------

class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        self._create_tables(cursor)
        self._seed_database(cursor)
        self.conn.commit()

    def _create_tables(self, cursor):
        for statement in CREATE_TABLE_STATEMENTS:
            cursor.execute(statement)

    def _seed_database(self, cursor):
        cursor.execute(COUNT_BOOKS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_BOOK_SQL, SEED_BOOKS)
            cursor.executemany(INSERT_MEMBER_SQL, SEED_MEMBERS)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_books(self, **params):
        title = params.get('title', '')
        author = params.get('author', '')
        genre = params.get('genre', '')
        available_only = params.get('available_only', 'false').lower() == 'true'
        query = _build_search_query(title, author, genre, available_only)
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            books = [_book_from_row(row) for row in cursor.fetchall()]
            return {'books': books}
        except Exception as e:
            cherrypy.response.status = STATUS_INTERNAL_SERVER_ERROR
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            book_id = params['book_id']
            member_id = params['member_id']
            loan_date = _current_date()
            # NOTE: ``timedelta`` is deliberately left unimported so that the
            # runtime behaviour (a NameError surfaced as a 400 response) is
            # identical to the original module.
            due_date = (datetime.now() + timedelta(days=LOAN_PERIOD_DAYS)).strftime(DATE_FORMAT)
            cursor = self.conn.cursor()
            cursor.execute(INSERT_LOAN_SQL, (book_id, member_id, loan_date, due_date))
            cursor.execute(DECREMENT_AVAILABLE_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except Exception as e:
            cherrypy.response.status = STATUS_BAD_REQUEST
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            loan_id = params['loan_id']
            return_date = _current_date()
            cursor = self.conn.cursor()
            cursor.execute(SELECT_LOAN_BOOK_ID_SQL, (loan_id,))
            book_id = cursor.fetchone()[0]
            cursor.execute(MARK_LOAN_RETURNED_SQL, (return_date, loan_id))
            cursor.execute(INCREMENT_AVAILABLE_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except Exception as e:
            cherrypy.response.status = STATUS_BAD_REQUEST
            return {'error': str(e)}


if __name__ == '__main__':
    cherrypy.config.update(SERVER_CONFIG)
    cherrypy.quickstart(LibrarySystem())
