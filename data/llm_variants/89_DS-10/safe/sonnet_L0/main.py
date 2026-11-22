from quart import Quart, request, jsonify
import sqlite3
import uuid
from datetime import datetime
import re

app = Quart(__name__)

DB_PATH = 'support.db'

CREATE_CUSTOMERS_SQL = '''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    '''

CREATE_TICKETS_SQL = '''
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
    '''

CREATE_RESPONSES_SQL = '''
        CREATE TABLE IF NOT EXISTS responses (
            response_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            responder TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
        )
    '''

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

VALID_STATUSES = ['open', 'in_progress', 'resolved', 'closed']

SEARCH_TICKETS_SQL = '''
            SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at, 
                   c.name as customer_name, c.email as customer_email
            FROM tickets t
            JOIN customers c ON t.customer_id = c.customer_id
            WHERE (t.subject LIKE ? OR t.description LIKE ?)
        '''

TICKET_FIELDS = ('ticket_id', 'subject', 'status', 'priority', 'created_at',
                 'customer_name', 'customer_email')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(CREATE_CUSTOMERS_SQL)
    cursor.execute(CREATE_TICKETS_SQL)
    cursor.execute(CREATE_RESPONSES_SQL)
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO customers (customer_id, name, email, phone)
            VALUES (?, ?, ?, ?)
        ''', SEED_CUSTOMERS)
        cursor.executemany('''
            INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', SEED_TICKETS)
    conn.commit()
    conn.close()


def validate_customer_id(customer_id):
    if not re.match('^CUST-\\d{4}$', customer_id):
        raise ValueError('Invalid customer ID format')
    return customer_id


def validate_ticket_id(ticket_id):
    if not re.match('^TICKET-\\d{4}$', ticket_id):
        raise ValueError('Invalid ticket ID format')
    return ticket_id


def validate_priority(priority):
    try:
        priority = int(priority)
        if priority < 1 or priority > 5:
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
    return re.sub('[;\\\'"\\\\]', '', term)


async def _error_response(message, status_code):
    return (await jsonify({'error': message}), status_code)


def _close_quietly(conn):
    if conn is not None:
        conn.close()


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

        conn = sqlite3.connect(DB_PATH)
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
        tickets = [dict(zip(TICKET_FIELDS, row)) for row in cursor.fetchall()]
        conn.close()
        return await jsonify({'tickets': tickets})
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        _close_quietly(conn)
        return await _error_response('Internal server error', 500)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    conn = None
    try:
        data = await request.get_json()
        required_fields = ['customer_id', 'subject', 'description']
        if not all(field in data for field in required_fields):
            return await _error_response('Missing required fields', 400)
        customer_id = validate_customer_id(data['customer_id'])
        priority = validate_priority(data.get('priority', 3))
        if len(data['subject']) > 200:
            return await _error_response('Subject too long', 400)
        if len(data['description']) > 2000:
            return await _error_response('Description too long', 400)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM customers WHERE customer_id = ?', (customer_id,))
        if not cursor.fetchone():
            conn.close()
            return await _error_response('Customer not found', 404)

        ticket_id = f'TICKET-{str(uuid.uuid4())[:4].upper()}'
        cursor.execute('''
            INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)
            VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, customer_id, data['subject'], data['description'], priority))
        conn.commit()
        conn.close()
        return (await jsonify({'ticket_id': ticket_id}), 201)
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        _close_quietly(conn)
        return await _error_response('Failed to create ticket', 500)


@app.route('/tickets/<ticket_id>/respond', methods=['POST'])
async def add_response(ticket_id):
    conn = None
    try:
        data = await request.get_json()
        if not all(field in data for field in ['responder', 'message']):
            return await _error_response('Missing required fields', 400)
        ticket_id = validate_ticket_id(ticket_id)
        if len(data['responder']) > 100:
            return await _error_response('Responder name too long', 400)
        if len(data['message']) > 2000:
            return await _error_response('Message too long', 400)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM tickets WHERE ticket_id = ?', (ticket_id,))
        if not cursor.fetchone():
            conn.close()
            return await _error_response('Ticket not found', 404)

        response_id = f'RESP-{str(uuid.uuid4())[:4].upper()}'
        cursor.execute('''
            INSERT INTO responses (response_id, ticket_id, responder, message)
            VALUES (?, ?, ?, ?)
        ''', (response_id, ticket_id, data['responder'], data['message']))
        conn.commit()
        conn.close()
        return (await jsonify({'response_id': response_id}), 201)
    except ValueError as e:
        return await _error_response(str(e), 400)
    except Exception:
        _close_quietly(conn)
        return await _error_response('Failed to add response', 500)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000, debug=False)
