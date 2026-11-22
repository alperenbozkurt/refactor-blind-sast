from contextlib import closing

from quart import Quart, request, jsonify
import sqlite3
import uuid
from datetime import datetime
import re

app = Quart(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
DB_PATH = 'support.db'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SERVER_DEBUG = False

CUSTOMER_ID_PATTERN = '^CUST-\\d{4}$'
TICKET_ID_PATTERN = '^TICKET-\\d{4}$'
SEARCH_TERM_STRIP_PATTERN = '[;\\\'"\\\\]'

VALID_STATUSES = ['open', 'in_progress', 'resolved', 'closed']
MIN_PRIORITY = 1
MAX_PRIORITY = 5
DEFAULT_PRIORITY = 3

MAX_SUBJECT_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_RESPONDER_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000

TICKET_ID_PREFIX = 'TICKET-'
RESPONSE_ID_PREFIX = 'RESP-'
GENERATED_ID_LENGTH = 4

CREATE_TICKET_REQUIRED_FIELDS = ['customer_id', 'subject', 'description']
ADD_RESPONSE_REQUIRED_FIELDS = ['responder', 'message']

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------
CREATE_CUSTOMERS_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS customers (\n            customer_id TEXT PRIMARY KEY,\n            name TEXT NOT NULL,\n            email TEXT UNIQUE NOT NULL,\n            phone TEXT,\n            registration_date TEXT DEFAULT CURRENT_TIMESTAMP\n        )\n    '
CREATE_TICKETS_TABLE_SQL = "\n        CREATE TABLE IF NOT EXISTS tickets (\n            ticket_id TEXT PRIMARY KEY,\n            customer_id TEXT NOT NULL,\n            subject TEXT NOT NULL,\n            description TEXT NOT NULL,\n            status TEXT DEFAULT 'open',\n            priority INTEGER DEFAULT 3,\n            created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n            resolved_at TEXT,\n            FOREIGN KEY(customer_id) REFERENCES customers(customer_id)\n        )\n    "
CREATE_RESPONSES_TABLE_SQL = '\n        CREATE TABLE IF NOT EXISTS responses (\n            response_id TEXT PRIMARY KEY,\n            ticket_id TEXT NOT NULL,\n            responder TEXT NOT NULL,\n            message TEXT NOT NULL,\n            created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n            FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)\n        )\n    '
SCHEMA_STATEMENTS = (
    CREATE_CUSTOMERS_TABLE_SQL,
    CREATE_TICKETS_TABLE_SQL,
    CREATE_RESPONSES_TABLE_SQL,
)

COUNT_CUSTOMERS_SQL = 'SELECT COUNT(*) FROM customers'
INSERT_CUSTOMER_SQL = '\n            INSERT INTO customers (customer_id, name, email, phone)\n            VALUES (?, ?, ?, ?)\n        '
INSERT_SEED_TICKET_SQL = '\n            INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)\n            VALUES (?, ?, ?, ?, ?, ?)\n        '

CUSTOMER_EXISTS_SQL = 'SELECT 1 FROM customers WHERE customer_id = ?'
TICKET_EXISTS_SQL = 'SELECT 1 FROM tickets WHERE ticket_id = ?'
INSERT_TICKET_SQL = '\n            INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)\n            VALUES (?, ?, ?, ?, ?)\n        '
INSERT_RESPONSE_SQL = '\n            INSERT INTO responses (response_id, ticket_id, responder, message)\n            VALUES (?, ?, ?, ?)\n        '

SEARCH_TICKETS_BASE_SQL = '\n            SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at, \n                   c.name as customer_name, c.email as customer_email\n            FROM tickets t\n            JOIN customers c ON t.customer_id = c.customer_id\n            WHERE (t.subject LIKE ? OR t.description LIKE ?)\n        '
SEARCH_STATUS_CLAUSE = ' AND t.status = ?'
SEARCH_PRIORITY_CLAUSE = ' AND t.priority = ?'
SEARCH_CUSTOMER_CLAUSE = ' AND t.customer_id = ?'

TICKET_SEARCH_FIELDS = (
    'ticket_id',
    'subject',
    'status',
    'priority',
    'created_at',
    'customer_name',
    'customer_email',
)

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


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _connect():
    return sqlite3.connect(DB_PATH)


def _record_exists(cursor, sql, key):
    cursor.execute(sql, (key,))
    return bool(cursor.fetchone())


def _generate_id(prefix):
    return f'{prefix}{str(uuid.uuid4())[:GENERATED_ID_LENGTH].upper()}'


def _create_schema(cursor):
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)


def _seed_database(cursor):
    cursor.execute(COUNT_CUSTOMERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_CUSTOMER_SQL, SEED_CUSTOMERS)
        cursor.executemany(INSERT_SEED_TICKET_SQL, SEED_TICKETS)


def init_db():
    conn = _connect()
    cursor = conn.cursor()
    _create_schema(cursor)
    _seed_database(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def validate_customer_id(customer_id):
    if not re.match(CUSTOMER_ID_PATTERN, customer_id):
        raise ValueError('Invalid customer ID format')
    return customer_id


def validate_ticket_id(ticket_id):
    if not re.match(TICKET_ID_PATTERN, ticket_id):
        raise ValueError('Invalid ticket ID format')
    return ticket_id


def validate_priority(priority):
    try:
        priority = int(priority)
        if priority < MIN_PRIORITY or priority > MAX_PRIORITY:
            raise ValueError('Priority must be between 1 and 5')
        return priority
    except ValueError:
        raise ValueError('Invalid priority value')


def validate_status(status):
    if status.lower() not in VALID_STATUSES:
        raise ValueError('Invalid status value')
    return status.lower()


def sanitize_search_term(term):
    if not term:
        return ''
    return re.sub(SEARCH_TERM_STRIP_PATTERN, '', term)


def _has_all_fields(data, fields):
    return all((field in data for field in fields))


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
async def _error_response(message, status_code):
    return (await jsonify({'error': message}), status_code)


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------
def _build_search_query(search_term, status, priority, customer_id):
    query = SEARCH_TICKETS_BASE_SQL
    params = [f'%{search_term}%', f'%{search_term}%']
    if status:
        query += SEARCH_STATUS_CLAUSE
        params.append(status)
    if priority:
        query += SEARCH_PRIORITY_CLAUSE
        params.append(priority)
    if customer_id:
        query += SEARCH_CUSTOMER_CLAUSE
        params.append(customer_id)
    return query, params


def _row_to_ticket(row):
    return dict(zip(TICKET_SEARCH_FIELDS, row))


def _search_tickets_in_db(search_term, status, priority, customer_id):
    query, params = _build_search_query(search_term, status, priority, customer_id)
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [_row_to_ticket(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Persistence for create operations
# ---------------------------------------------------------------------------
def _insert_ticket(customer_id, subject, description, priority):
    """Insert a ticket; return its id, or None if the customer is unknown."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        if not _record_exists(cursor, CUSTOMER_EXISTS_SQL, customer_id):
            return None
        ticket_id = _generate_id(TICKET_ID_PREFIX)
        cursor.execute(
            INSERT_TICKET_SQL,
            (ticket_id, customer_id, subject, description, priority),
        )
        conn.commit()
        return ticket_id


def _insert_response(ticket_id, responder, message):
    """Insert a response; return its id, or None if the ticket is unknown."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        if not _record_exists(cursor, TICKET_EXISTS_SQL, ticket_id):
            return None
        response_id = _generate_id(RESPONSE_ID_PREFIX)
        cursor.execute(
            INSERT_RESPONSE_SQL,
            (response_id, ticket_id, responder, message),
        )
        conn.commit()
        return response_id


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/tickets/search', methods=['GET'])
async def search_tickets():
    try:
        search_term = sanitize_search_term(request.args.get('q', ''))
        status = request.args.get('status', '')
        priority = request.args.get('priority', '')
        customer_id = request.args.get('customer_id', '')
        if status:
            status = validate_status(status)
        if priority:
            priority = validate_priority(priority)
        if customer_id:
            customer_id = validate_customer_id(customer_id)
        tickets = _search_tickets_in_db(search_term, status, priority, customer_id)
        return await jsonify({'tickets': tickets})
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        return await _error_response('Internal server error', 500)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    try:
        data = await request.get_json()
        if not _has_all_fields(data, CREATE_TICKET_REQUIRED_FIELDS):
            return await _error_response('Missing required fields', 400)
        customer_id = validate_customer_id(data['customer_id'])
        priority = validate_priority(data.get('priority', DEFAULT_PRIORITY))
        if len(data['subject']) > MAX_SUBJECT_LENGTH:
            return await _error_response('Subject too long', 400)
        if len(data['description']) > MAX_DESCRIPTION_LENGTH:
            return await _error_response('Description too long', 400)
        ticket_id = _insert_ticket(
            customer_id, data['subject'], data['description'], priority
        )
        if ticket_id is None:
            return await _error_response('Customer not found', 404)
        return (await jsonify({'ticket_id': ticket_id}), 201)
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        return await _error_response('Failed to create ticket', 500)


@app.route('/tickets/<ticket_id>/respond', methods=['POST'])
async def add_response(ticket_id):
    try:
        data = await request.get_json()
        if not _has_all_fields(data, ADD_RESPONSE_REQUIRED_FIELDS):
            return await _error_response('Missing required fields', 400)
        ticket_id = validate_ticket_id(ticket_id)
        if len(data['responder']) > MAX_RESPONDER_LENGTH:
            return await _error_response('Responder name too long', 400)
        if len(data['message']) > MAX_MESSAGE_LENGTH:
            return await _error_response('Message too long', 400)
        response_id = _insert_response(ticket_id, data['responder'], data['message'])
        if response_id is None:
            return await _error_response('Ticket not found', 404)
        return (await jsonify({'response_id': response_id}), 201)
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        return await _error_response('Failed to add response', 500)


if __name__ == '__main__':
    init_db()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
