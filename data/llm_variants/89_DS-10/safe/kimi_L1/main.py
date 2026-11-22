"""Customer support ticket API backed by a SQLite database."""

import re
import sqlite3
import uuid
from datetime import datetime  # noqa: F401  (kept to preserve the module namespace)

from quart import Quart, jsonify, request

app = Quart(__name__)

DATABASE_PATH = 'support.db'

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

SEED_CUSTOMERS_SQL = """
    INSERT INTO customers (customer_id, name, email, phone)
    VALUES (?, ?, ?, ?)
"""

SEED_TICKETS_SQL = """
    INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)
    VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_TICKET_SQL = """
    INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)
    VALUES (?, ?, ?, ?, ?)
"""

INSERT_RESPONSE_SQL = """
    INSERT INTO responses (response_id, ticket_id, responder, message)
    VALUES (?, ?, ?, ?)
"""

SELECT_CUSTOMER_SQL = 'SELECT 1 FROM customers WHERE customer_id = ?'
SELECT_TICKET_SQL = 'SELECT 1 FROM tickets WHERE ticket_id = ?'

SEARCH_TICKETS_SQL = """
    SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at,
           c.name as customer_name, c.email as customer_email
    FROM tickets t
    JOIN customers c ON t.customer_id = c.customer_id
    WHERE (t.subject LIKE ? OR t.description LIKE ?)
"""

# ---------------------------------------------------------------------------
# Seed data (inserted only when the customers table is empty)
# ---------------------------------------------------------------------------

SEED_CUSTOMERS = (
    ('CUST-1001', 'Alice Johnson', 'alice@example.com', '555-0101'),
    ('CUST-1002', 'Bob Smith', 'bob@example.com', '555-0102'),
    ('CUST-1003', 'Charlie Brown', 'charlie@example.com', '555-0103'),
)

SEED_TICKETS = (
    ('TICKET-1001', 'CUST-1001', 'Login issues', 'Cannot login to my account', 'open', 2),
    ('TICKET-1002', 'CUST-1002', 'Payment problem', 'Payment not processed', 'resolved', 1),
    ('TICKET-1003', 'CUST-1003', 'Feature request', 'Add dark mode', 'open', 3),
)

# ---------------------------------------------------------------------------
# Validation rules and field limits
# ---------------------------------------------------------------------------

CUSTOMER_ID_PATTERN = re.compile(r'^CUST-\d{4}$')
TICKET_ID_PATTERN = re.compile(r'^TICKET-\d{4}$')
SEARCH_TERM_STRIP_PATTERN = re.compile(r'[;\'"\\]')

VALID_STATUSES = ('open', 'in_progress', 'resolved', 'closed')
MIN_PRIORITY = 1
MAX_PRIORITY = 5
DEFAULT_PRIORITY = 3

MAX_SUBJECT_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_RESPONDER_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000

REQUIRED_TICKET_FIELDS = ('customer_id', 'subject', 'description')
REQUIRED_RESPONSE_FIELDS = ('responder', 'message')

SEARCH_RESULT_FIELDS = (
    'ticket_id',
    'subject',
    'status',
    'priority',
    'created_at',
    'customer_name',
    'customer_email',
)


def get_db_connection():
    """Open a new connection to the support database."""
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(CREATE_CUSTOMERS_TABLE_SQL)
    cursor.execute(CREATE_TICKETS_TABLE_SQL)
    cursor.execute(CREATE_RESPONSES_TABLE_SQL)

    cursor.execute(COUNT_CUSTOMERS_SQL)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(SEED_CUSTOMERS_SQL, SEED_CUSTOMERS)
        cursor.executemany(SEED_TICKETS_SQL, SEED_TICKETS)

    conn.commit()
    conn.close()


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
    if status.lower() not in VALID_STATUSES:
        raise ValueError('Invalid status value')
    return status.lower()


def sanitize_search_term(term):
    if not term:
        return ''
    return SEARCH_TERM_STRIP_PATTERN.sub('', term)


async def error_response(message, status_code):
    """Build a JSON error body paired with the given HTTP status code."""
    return (await jsonify({'error': message}), status_code)


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

        conn = get_db_connection()
        cursor = conn.cursor()

        query = SEARCH_TICKETS_SQL
        params = [f'%{search_term}%', f'%{search_term}%']
        if status:
            query += ' AND t.status = ?'
            params.append(status)
        if priority:
            query += ' AND t.priority = ?'
            params.append(priority)
        if customer_id:
            query += ' AND t.customer_id = ?'
            params.append(customer_id)

        cursor.execute(query, params)
        tickets = [dict(zip(SEARCH_RESULT_FIELDS, row)) for row in cursor.fetchall()]
        conn.close()
        return await jsonify({'tickets': tickets})
    except ValueError as e:
        return await error_response(str(e), 400)
    except Exception:
        if 'conn' in locals():
            conn.close()
        return await error_response('Internal server error', 500)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    try:
        data = await request.get_json()
        if not all(field in data for field in REQUIRED_TICKET_FIELDS):
            return await error_response('Missing required fields', 400)

        customer_id = validate_customer_id(data['customer_id'])
        priority = validate_priority(data.get('priority', DEFAULT_PRIORITY))

        if len(data['subject']) > MAX_SUBJECT_LENGTH:
            return await error_response('Subject too long', 400)
        if len(data['description']) > MAX_DESCRIPTION_LENGTH:
            return await error_response('Description too long', 400)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(SELECT_CUSTOMER_SQL, (customer_id,))
        if not cursor.fetchone():
            conn.close()
            return await error_response('Customer not found', 404)

        ticket_id = f'TICKET-{str(uuid.uuid4())[:4].upper()}'
        cursor.execute(
            INSERT_TICKET_SQL,
            (ticket_id, customer_id, data['subject'], data['description'], priority),
        )
        conn.commit()
        conn.close()
        return (await jsonify({'ticket_id': ticket_id}), 201)
    except ValueError as e:
        return await error_response(str(e), 400)
    except Exception:
        if 'conn' in locals():
            conn.close()
        return await error_response('Failed to create ticket', 500)


@app.route('/tickets/<ticket_id>/respond', methods=['POST'])
async def add_response(ticket_id):
    try:
        data = await request.get_json()
        if not all(field in data for field in REQUIRED_RESPONSE_FIELDS):
            return await error_response('Missing required fields', 400)

        ticket_id = validate_ticket_id(ticket_id)

        if len(data['responder']) > MAX_RESPONDER_LENGTH:
            return await error_response('Responder name too long', 400)
        if len(data['message']) > MAX_MESSAGE_LENGTH:
            return await error_response('Message too long', 400)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(SELECT_TICKET_SQL, (ticket_id,))
        if not cursor.fetchone():
            conn.close()
            return await error_response('Ticket not found', 404)

        response_id = f'RESP-{str(uuid.uuid4())[:4].upper()}'
        cursor.execute(
            INSERT_RESPONSE_SQL,
            (response_id, ticket_id, data['responder'], data['message']),
        )
        conn.commit()
        conn.close()
        return (await jsonify({'response_id': response_id}), 201)
    except ValueError as e:
        return await error_response(str(e), 400)
    except Exception:
        if 'conn' in locals():
            conn.close()
        return await error_response('Failed to add response', 500)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000, debug=False)
