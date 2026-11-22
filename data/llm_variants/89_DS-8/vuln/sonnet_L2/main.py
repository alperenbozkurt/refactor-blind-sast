import cherrypy
import sqlite3
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DATABASE_PATH = 'library.db'
SERVER_CONFIG = {'server.socket_port': 8080}

DATE_FORMAT = '%Y-%m-%d'
LOAN_PERIOD_DAYS = 14

STATUS_SERVER_ERROR = 500
STATUS_BAD_REQUEST = 400

BOOK_COLUMNS = (
    'book_id',
    'title',
    'author',
    'isbn',
    'published_date',
    'genre',
    'available_copies',
)

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_BOOKS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS books (\n                book_id INTEGER PRIMARY KEY,\n                title TEXT NOT NULL,\n                author TEXT NOT NULL,\n                isbn TEXT UNIQUE NOT NULL,\n                published_date TEXT,\n                genre TEXT,\n                available_copies INTEGER DEFAULT 1\n            )\n        '
CREATE_MEMBERS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS members (\n                member_id INTEGER PRIMARY KEY,\n                name TEXT NOT NULL,\n                email TEXT UNIQUE NOT NULL,\n                join_date TEXT DEFAULT CURRENT_TIMESTAMP\n            )\n        '
CREATE_LOANS_TABLE_SQL = '\n            CREATE TABLE IF NOT EXISTS loans (\n                loan_id INTEGER PRIMARY KEY,\n                book_id INTEGER NOT NULL,\n                member_id INTEGER NOT NULL,\n                loan_date TEXT NOT NULL,\n                due_date TEXT NOT NULL,\n                return_date TEXT,\n                FOREIGN KEY(book_id) REFERENCES books(book_id),\n                FOREIGN KEY(member_id) REFERENCES members(member_id)\n            )\n        '
SCHEMA_STATEMENTS = (
    CREATE_BOOKS_TABLE_SQL,
    CREATE_MEMBERS_TABLE_SQL,
    CREATE_LOANS_TABLE_SQL,
)

COUNT_BOOKS_SQL = 'SELECT COUNT(*) FROM books'
INSERT_BOOK_SQL = '\n                INSERT INTO books (title, author, isbn, published_date, genre, available_copies)\n                VALUES (?, ?, ?, ?, ?, ?)\n            '
INSERT_MEMBER_SQL = '\n                INSERT INTO members (name, email)\n                VALUES (?, ?)\n            '
INSERT_LOAN_SQL = '\n                INSERT INTO loans (book_id, member_id, loan_date, due_date)\n                VALUES (?, ?, ?, ?)\n            '
DECREMENT_COPIES_SQL = '\n                UPDATE books SET available_copies = available_copies - 1\n                WHERE book_id = ?\n            '
INCREMENT_COPIES_SQL = '\n                UPDATE books SET available_copies = available_copies + 1\n                WHERE book_id = ?\n            '
SELECT_LOAN_BOOK_SQL = 'SELECT book_id FROM loans WHERE loan_id = ?'
UPDATE_LOAN_RETURN_SQL = '\n                UPDATE loans SET return_date = ?\n                WHERE loan_id = ?\n            '

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_BOOKS = [
    ('Python Programming', 'John Smith', '978-0123456789', '2020-01-15', 'Technology', 3),
    ('Data Science Basics', 'Alice Johnson', '978-9876543210', '2019-05-20', 'Technology', 2),
    ('History of Art', 'Robert Brown', '978-5555555555', '2018-11-30', 'Art', 1),
]
SEED_MEMBERS = [
    ('Tom Wilson', 'tom@example.com'),
    ('Sarah Davis', 'sarah@example.com'),
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _today_string():
    """Return today's date formatted for storage."""
    return datetime.now().strftime(DATE_FORMAT)


def _due_date_string():
    """Return the due date for a loan starting now.

    Note: preserves original behaviour, where ``timedelta`` is not imported
    and therefore raises ``NameError`` at call time.
    """
    return (datetime.now() + timedelta(days=LOAN_PERIOD_DAYS)).strftime(DATE_FORMAT)


def _book_row_to_dict(row):
    """Convert a books table row into a JSON-serialisable dict."""
    return {column: row[index] for index, column in enumerate(BOOK_COLUMNS)}


def _build_search_query(title, author, genre, available_only):
    """Build the book search SQL query from the given filters."""
    query = f"SELECT * FROM books WHERE title LIKE '%{title}%'"
    if author:
        query += f" AND author LIKE '%{author}%'"
    if genre:
        query += f" AND genre LIKE '%{genre}%'"
    if available_only:
        query += ' AND available_copies > 0'
    return query


def _error_response(status, error):
    """Set the HTTP status and build a JSON error payload."""
    cherrypy.response.status = status
    return {'error': str(error)}


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class LibrarySystem:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        self._create_schema(cursor)
        self._seed_if_empty(cursor)
        self.conn.commit()

    def _create_schema(self, cursor):
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)

    def _seed_if_empty(self, cursor):
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
            books = [_book_row_to_dict(row) for row in cursor.fetchall()]
            return {'books': books}
        except Exception as e:
            return _error_response(STATUS_SERVER_ERROR, e)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def borrow_book(self, **params):
        try:
            book_id = params['book_id']
            member_id = params['member_id']
            loan_date = _today_string()
            due_date = _due_date_string()
            cursor = self.conn.cursor()
            cursor.execute(INSERT_LOAN_SQL, (book_id, member_id, loan_date, due_date))
            cursor.execute(DECREMENT_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success', 'loan_id': cursor.lastrowid}
        except Exception as e:
            return _error_response(STATUS_BAD_REQUEST, e)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def return_book(self, **params):
        try:
            loan_id = params['loan_id']
            return_date = _today_string()
            cursor = self.conn.cursor()
            cursor.execute(SELECT_LOAN_BOOK_SQL, (loan_id,))
            book_id = cursor.fetchone()[0]
            cursor.execute(UPDATE_LOAN_RETURN_SQL, (return_date, loan_id))
            cursor.execute(INCREMENT_COPIES_SQL, (book_id,))
            self.conn.commit()
            return {'status': 'success'}
        except Exception as e:
            return _error_response(STATUS_BAD_REQUEST, e)


if __name__ == '__main__':
    cherrypy.config.update(SERVER_CONFIG)
    cherrypy.quickstart(LibrarySystem())
