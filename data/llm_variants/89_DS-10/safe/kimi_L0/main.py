import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime

from quart import Quart, jsonify, request

app = Quart(__name__)

DATABASE = 'support.db'

CUSTOMER_ID_PATTERN = re.compile(r'^CUST-\d{4}$')
TICKET_ID_PATTERN = re.compile(r'^TICKET-\d{4}$')
UNSAFE_SEARCH_CHARS_PATTERN = re.compile(r'[;\'"\\]')

VALID_STATUSES = ('open', 'in_progress', 'resolved', 'closed')
DEFAULT_PRIORITY = 3

MAX_SUBJECT_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_RESPONDER_LENGTH = 100
MAX_MESSAGE_LENGTH = 2000

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        registration_date TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
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
    """,
    """
    CREATE TABLE IF NOT EXISTS responses (
        response_id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL,
        responder TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
    )
    """,
)

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

SEARCH_TICKETS_QUERY = """
    SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at,
           c.name as customer_name, c.email as customer_email
    FROM tickets t
    JOIN customers c ON t.customer_id = c.customer_id
    WHERE (t.subject LIKE ? OR t.description LIKE ?)
"""

TICKET_RESULT_COLUMNS = (
    'ticket_id',
    'subject',
    'status',
    'priority',
    'created_at',
    'customer_name',
    'customer_email',
)


def get_connection():
    return sqlite3.connect(DATABASE)


def init_db():
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        cursor.execute('SELECT COUNT(*) FROM customers')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                """
                INSERT INTO customers (customer_id, name, email, phone)
                VALUES (?, ?, ?, ?)
                """,
                SEED_CUSTOMERS,
            )
            cursor.executemany(
                """
                INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                SEED_TICKETS,
            )
        conn.commit()


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
        if not 1 <= priority <= 5:
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
    return UNSAFE_SEARCH_CHARS_PATTERN.sub('', term)


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

        query = SEARCH_TICKETS_QUERY
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

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            tickets = [
                dict(zip(TICKET_RESULT_COLUMNS, row)) for row in cursor.fetchall()
            ]
        return await jsonify({'tickets': tickets})
    except ValueError as e:
        return (await jsonify({'error': str(e)}), 400)
    except Exception:
        return (await jsonify({'error': 'Internal server error'}), 500)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    try:
        data = await request.get_json()
        required_fields = ['customer_id', 'subject', 'description']
        if not all(field in data for field in required_fields):
            return (await jsonify({'error': 'Missing required fields'}), 400)

        customer_id = validate_customer_id(data['customer_id'])
        priority = validate_priority(data.get('priority', DEFAULT_PRIORITY))
        if len(data['subject']) > MAX_SUBJECT_LENGTH:
            return (await jsonify({'error': 'Subject too long'}), 400)
        if len(data['description']) > MAX_DESCRIPTION_LENGTH:
            return (await jsonify({'error': 'Description too long'}), 400)

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM customers WHERE customer_id = ?', (customer_id,)
            )
            if not cursor.fetchone():
                return (await jsonify({'error': 'Customer not found'}), 404)

            ticket_id = f'TICKET-{str(uuid.uuid4())[:4].upper()}'
            cursor.execute(
                """
                INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ticket_id, customer_id, data['subject'], data['description'], priority),
            )
            conn.commit()
        return (await jsonify({'ticket_id': ticket_id}), 201)
    except ValueError as e:
        return (await jsonify({'error': str(e)}), 400)
    except Exception:
        return (await jsonify({'error': 'Failed to create ticket'}), 500)


@app.route('/tickets/<ticket_id>/respond', methods=['POST'])
async def add_response(ticket_id):
    try:
        data = await request.get_json()
        if not all(field in data for field in ['responder', 'message']):
            return (await jsonify({'error': 'Missing required fields'}), 400)

        ticket_id = validate_ticket_id(ticket_id)
        if len(data['responder']) > MAX_RESPONDER_LENGTH:
            return (await jsonify({'error': 'Responder name too long'}), 400)
        if len(data['message']) > MAX_MESSAGE_LENGTH:
            return (await jsonify({'error': 'Message too long'}), 400)

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM tickets WHERE ticket_id = ?', (ticket_id,))
            if not cursor.fetchone():
                return (await jsonify({'error': 'Ticket not found'}), 404)

            response_id = f'RESP-{str(uuid.uuid4())[:4].upper()}'
            cursor.execute(
                """
                INSERT INTO responses (response_id, ticket_id, responder, message)
                VALUES (?, ?, ?, ?)
                """,
                (response_id, ticket_id, data['responder'], data['message']),
            )
            conn.commit()
        return (await jsonify({'response_id': response_id}), 201)
    except ValueError as e:
        return (await jsonify({'error': str(e)}), 400)
    except Exception:
        return (await jsonify({'error': 'Failed to add response'}), 500)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000, debug=False)
