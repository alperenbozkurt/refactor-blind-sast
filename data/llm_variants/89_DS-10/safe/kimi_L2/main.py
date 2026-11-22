"""Customer support ticketing service.

A Quart + SQLite application exposing endpoints to search and create
support tickets and to add responses to existing tickets.

The public interface of this module (module-level names, routes and the
command-line entry point) is unchanged; the internals have been organised
into a frozen configuration object, named constants and small helpers.
"""

import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime  # noqa: F401  (preserved module-level name)

from quart import Quart, jsonify, request


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the support service."""

    database_path: str = 'support.db'
    host: str = '0.0.0.0'
    port: int = 8000
    debug: bool = False


CONFIG = AppConfig()

app = Quart(__name__)


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

CUSTOMER_ID_PATTERN = re.compile(r'^CUST-\d{4}$')
TICKET_ID_PATTERN = re.compile(r'^TICKET-\d{4}$')

# Characters stripped from user supplied search terms: ; ' " \
SANITIZE_PATTERN = re.compile('[;\\\'"\\\\]')

VALID_STATUSES = ('open', 'in_progress', 'resolved', 'closed')

MIN_PRIORITY = 1
MAX_PRIORITY = 5
DEFAULT_PRIORITY = 3

MAX_SUBJECT_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_RESPONDER_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000

TICKET_ID_PREFIX = 'TICKET'
RESPONSE_ID_PREFIX = 'RESP'

REQUIRED_TICKET_FIELDS = ('customer_id', 'subject', 'description')
REQUIRED_RESPONSE_FIELDS = ('responder', 'message')


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_CUSTOMERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        registration_date TEXT DEFAULT CURRENT_TIMESTAMP
    )
"""

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

CREATE_RESPONSES_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS responses (
        response_id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL,
        responder TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
    )
"""

COUNT_CUSTOMERS_SQL = 'SELECT COUNT(*) FROM customers'
CUSTOMER_EXISTS_SQL = 'SELECT 1 FROM customers WHERE customer_id = ?'
TICKET_EXISTS_SQL = 'SELECT 1 FROM tickets WHERE ticket_id = ?'

INSERT_CUSTOMER_SQL = """
    INSERT INTO customers (customer_id, name, email, phone)
    VALUES (?, ?, ?, ?)
"""

INSERT_TICKET_SQL = """
    INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)
    VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_NEW_TICKET_SQL = """
    INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)
    VALUES (?, ?, ?, ?, ?)
"""

INSERT_RESPONSE_SQL = """
    INSERT INTO responses (response_id, ticket_id, responder, message)
    VALUES (?, ?, ?, ?)
"""

SEARCH_TICKETS_QUERY = """
    SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at,
           c.name as customer_name, c.email as customer_email
    FROM tickets t
    JOIN customers c ON t.customer_id = c.customer_id
    WHERE (t.subject LIKE ? OR t.description LIKE ?)
"""

STATUS_FILTER_SQL = ' AND t.status = ?'
PRIORITY_FILTER_SQL = ' AND t.priority = ?'
CUSTOMER_ID_FILTER_SQL = ' AND t.customer_id = ?'


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

def _get_connection():
    return sqlite3.connect(CONFIG.database_path)


def _close_connection(conn):
    if conn is not None:
        conn.close()


def _create_tables(cursor):
    cursor.execute(CREATE_CUSTOMERS_TABLE_SQL)
    cursor.execute(CREATE_TICKETS_TABLE_SQL)
    cursor.execute(CREATE_RESPONSES_TABLE_SQL)


def _customers_table_is_empty(cursor):
    cursor.execute(COUNT_CUSTOMERS_SQL)
    return cursor.fetchone()[0] == 0


def _seed_database(cursor):
    cursor.executemany(INSERT_CUSTOMER_SQL, SEED_CUSTOMERS)
    cursor.executemany(INSERT_TICKET_SQL, SEED_TICKETS)


def _customer_exists(cursor, customer_id):
    cursor.execute(CUSTOMER_EXISTS_SQL, (customer_id,))
    return cursor.fetchone() is not None


def _ticket_exists(cursor, ticket_id):
    cursor.execute(TICKET_EXISTS_SQL, (ticket_id,))
    return cursor.fetchone() is not None


def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    _create_tables(cursor)
    if _customers_table_is_empty(cursor):
        _seed_database(cursor)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Validation (public API)
# ---------------------------------------------------------------------------

def validate_customer_id(customer_id):
    if not CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError('Invalid customer ID format')
    return customer_id


def validate_ticket_id(ticket_id):
    if not TICKET_ID_PATTERN.match(ticket_id):
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
    status = status.lower()
    if status not in VALID_STATUSES:
        raise ValueError('Invalid status value')
    return status


def sanitize_search_term(term):
    if not term:
        return ''
    return SANITIZE_PATTERN.sub('', term)


# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------

async def _error_response(message, status_code):
    return await jsonify({'error': message}), status_code


def _has_required_fields(data, required_fields):
    return all(field in data for field in required_fields)


def _generate_id(prefix):
    return f'{prefix}-{str(uuid.uuid4())[:4].upper()}'


def _build_search_query(search_term, status, priority, customer_id):
    query = SEARCH_TICKETS_QUERY
    params = [f'%{search_term}%', f'%{search_term}%']
    if status:
        query += STATUS_FILTER_SQL
        params.append(status)
    if priority:
        query += PRIORITY_FILTER_SQL
        params.append(priority)
    if customer_id:
        query += CUSTOMER_ID_FILTER_SQL
        params.append(customer_id)
    return query, params


def _ticket_row_to_dict(row):
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
# Routes
# ---------------------------------------------------------------------------

@app.route('/tickets/search', methods=['GET'])
async def search_tickets():
    conn = None
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
        conn = _get_connection()
        cursor = conn.cursor()
        query, params = _build_search_query(search_term, status, priority, customer_id)
        cursor.execute(query, params)
        tickets = [_ticket_row_to_dict(row) for row in cursor.fetchall()]
        conn.close()
        return await jsonify({'tickets': tickets})
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        _close_connection(conn)
        return await _error_response('Internal server error', 500)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    conn = None
    try:
        data = await request.get_json()
        if not _has_required_fields(data, REQUIRED_TICKET_FIELDS):
            return await _error_response('Missing required fields', 400)
        customer_id = validate_customer_id(data['customer_id'])
        priority = validate_priority(data.get('priority', DEFAULT_PRIORITY))
        if len(data['subject']) > MAX_SUBJECT_LENGTH:
            return await _error_response('Subject too long', 400)
        if len(data['description']) > MAX_DESCRIPTION_LENGTH:
            return await _error_response('Description too long', 400)
        conn = _get_connection()
        cursor = conn.cursor()
        if not _customer_exists(cursor, customer_id):
            conn.close()
            return await _error_response('Customer not found', 404)
        ticket_id = _generate_id(TICKET_ID_PREFIX)
        cursor.execute(
            INSERT_NEW_TICKET_SQL,
            (ticket_id, customer_id, data['subject'], data['description'], priority),
        )
        conn.commit()
        conn.close()
        return await jsonify({'ticket_id': ticket_id}), 201
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        _close_connection(conn)
        return await _error_response('Failed to create ticket', 500)


@app.route('/tickets/<ticket_id>/respond', methods=['POST'])
async def add_response(ticket_id):
    conn = None
    try:
        data = await request.get_json()
        if not _has_required_fields(data, REQUIRED_RESPONSE_FIELDS):
            return await _error_response('Missing required fields', 400)
        ticket_id = validate_ticket_id(ticket_id)
        if len(data['responder']) > MAX_RESPONDER_LENGTH:
            return await _error_response('Responder name too long', 400)
        if len(data['message']) > MAX_MESSAGE_LENGTH:
            return await _error_response('Message too long', 400)
        conn = _get_connection()
        cursor = conn.cursor()
        if not _ticket_exists(cursor, ticket_id):
            conn.close()
            return await _error_response('Ticket not found', 404)
        response_id = _generate_id(RESPONSE_ID_PREFIX)
        cursor.execute(
            INSERT_RESPONSE_SQL,
            (response_id, ticket_id, data['responder'], data['message']),
        )
        conn.commit()
        conn.close()
        return await jsonify({'response_id': response_id}), 201
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        _close_connection(conn)
        return await _error_response('Failed to add response', 500)


if __name__ == '__main__':
    init_db()
    app.run(host=CONFIG.host, port=CONFIG.port, debug=CONFIG.debug)
