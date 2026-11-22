"""Customer support ticket service.

A Quart application backed by SQLite that exposes endpoints to search
support tickets, create new tickets and add responses to existing ones.
"""

from quart import Quart, request, jsonify
import sqlite3
import uuid
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DATABASE_PATH = 'support.db'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

DEFAULT_TICKET_PRIORITY = 3

TICKET_ID_PREFIX = 'TICKET'
RESPONSE_ID_PREFIX = 'RESP'
GENERATED_ID_SUFFIX_LENGTH = 4

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_CUSTOMERS_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    '''

CREATE_TICKETS_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            priority INTEGER DEFAULT 3,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
        )
    """

CREATE_RESPONSES_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS responses (
            response_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            responder TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
        )
    '''

COUNT_CUSTOMERS_SQL = 'SELECT COUNT(*) FROM customers'

INSERT_CUSTOMER_SQL = '''
            INSERT INTO customers (customer_id, name, email, phone)
            VALUES (?, ?, ?, ?)
        '''

INSERT_SEED_TICKET_SQL = '''
            INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        '''

INSERT_TICKET_SQL = '''
            INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_RESPONSE_SQL = '''
            INSERT INTO responses (response_id, ticket_id, responder, message)
            VALUES (?, ?, ?, ?)
        '''

SEARCH_TICKETS_BASE_SQL = """
        SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at, 
               c.name as customer_name, c.email as customer_email
        FROM tickets t
        JOIN customers c ON t.customer_id = c.customer_id
        WHERE (t.subject LIKE '%{search_term}%' OR t.description LIKE '%{search_term}%')
    """

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_CUSTOMERS = [
    ('CUST-1001', 'Alice Johnson', 'alice@example.com', '555-0101'),
    ('CUST-1002', 'Bob Smith', 'bob@example.com', '555-0102'),
    ('CUST-1003', 'Charlie Brown', 'charlie@example.com', '555-0103'),
]

SEED_TICKETS = [
    ('TICKET-1001', 'CUST-1001', 'Login issues', 'Cannot login to my account', 'open', 2),
    ('TICKET-1002', 'CUST-1002', 'Payment problem', 'Payment not processed', 'resolved', 1),
    ('TICKET-1003', 'CUST-1003', 'Feature request', 'Add dark mode', 'open', 3),
]

app = Quart(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _connect():
    """Return a new connection to the support database."""
    return sqlite3.connect(DATABASE_PATH)


def _generate_id(prefix):
    """Return a short unique identifier such as ``TICKET-1A2B``."""
    suffix = str(uuid.uuid4())[:GENERATED_ID_SUFFIX_LENGTH].upper()
    return f'{prefix}-{suffix}'


def _create_tables(cursor):
    """Create the database schema if it does not already exist."""
    cursor.execute(CREATE_CUSTOMERS_TABLE_SQL)
    cursor.execute(CREATE_TICKETS_TABLE_SQL)
    cursor.execute(CREATE_RESPONSES_TABLE_SQL)


def _seed_database(cursor):
    """Insert the default customers and tickets into an empty database."""
    cursor.execute(COUNT_CUSTOMERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_CUSTOMER_SQL, SEED_CUSTOMERS)
        cursor.executemany(INSERT_SEED_TICKET_SQL, SEED_TICKETS)


def _build_search_query(search_term, status, priority, customer_id):
    """Build the ticket search SQL for the given filter values."""
    query = SEARCH_TICKETS_BASE_SQL.format(search_term=search_term)
    if status:
        query += f" AND t.status = '{status}'"
    if priority:
        query += f' AND t.priority = {priority}'
    if customer_id:
        query += f" AND t.customer_id = '{customer_id}'"
    return query


def _search_row_to_ticket(row):
    """Convert a ticket search result row into a JSON-ready dict."""
    return {
        'ticket_id': row[0],
        'subject': row[1],
        'status': row[2],
        'priority': row[3],
        'created_at': row[4],
        'customer_name': row[5],
        'customer_email': row[6],
    }


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db():
    conn = _connect()
    cursor = conn.cursor()
    _create_tables(cursor)
    _seed_database(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/tickets/search', methods=['GET'])
async def search_tickets():
    search_term = request.args.get('q', '')
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    customer_id = request.args.get('customer_id', '')

    conn = _connect()
    cursor = conn.cursor()
    query = _build_search_query(search_term, status, priority, customer_id)
    try:
        cursor.execute(query)
        tickets = [_search_row_to_ticket(row) for row in cursor.fetchall()]
        conn.close()
        return await jsonify({'tickets': tickets})
    except Exception as e:
        conn.close()
        return (await jsonify({'error': str(e)}), 500)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    try:
        data = await request.get_json()
        conn = _connect()
        cursor = conn.cursor()
        ticket_id = _generate_id(TICKET_ID_PREFIX)
        cursor.execute(INSERT_TICKET_SQL, (
            ticket_id,
            data['customer_id'],
            data['subject'],
            data['description'],
            data.get('priority', DEFAULT_TICKET_PRIORITY),
        ))
        conn.commit()
        conn.close()
        return (await jsonify({'ticket_id': ticket_id}), 201)
    except Exception as e:
        return (await jsonify({'error': str(e)}), 400)


@app.route('/tickets/<ticket_id>/respond', methods=['POST'])
async def add_response(ticket_id):
    try:
        data = await request.get_json()
        conn = _connect()
        cursor = conn.cursor()
        response_id = _generate_id(RESPONSE_ID_PREFIX)
        cursor.execute(INSERT_RESPONSE_SQL, (
            response_id,
            ticket_id,
            data['responder'],
            data['message'],
        ))
        conn.commit()
        conn.close()
        return (await jsonify({'response_id': response_id}), 201)
    except Exception as e:
        return (await jsonify({'error': str(e)}), 400)


if __name__ == '__main__':
    init_db()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
