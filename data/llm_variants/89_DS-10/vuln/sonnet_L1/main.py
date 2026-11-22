from quart import Quart, request, jsonify
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime

app = Quart(__name__)

DB_PATH = 'support.db'

CREATE_CUSTOMERS_TABLE = """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """

CREATE_TICKETS_TABLE = """
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

CREATE_RESPONSES_TABLE = """
        CREATE TABLE IF NOT EXISTS responses (
            response_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            responder TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
        )
    """

INSERT_CUSTOMER = """
            INSERT INTO customers (customer_id, name, email, phone)
            VALUES (?, ?, ?, ?)
        """

INSERT_SEED_TICKET = """
            INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        """

INSERT_TICKET = """
            INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)
            VALUES (?, ?, ?, ?, ?)
        """

INSERT_RESPONSE = """
            INSERT INTO responses (response_id, ticket_id, responder, message)
            VALUES (?, ?, ?, ?)
        """

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

TICKET_SEARCH_FIELDS = (
    'ticket_id',
    'subject',
    'status',
    'priority',
    'created_at',
    'customer_name',
    'customer_email',
)


def _connect():
    return sqlite3.connect(DB_PATH)


def _generate_id(prefix):
    return f'{prefix}-{str(uuid.uuid4())[:4].upper()}'


def _seed_database(cursor):
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_CUSTOMER, SEED_CUSTOMERS)
        cursor.executemany(INSERT_SEED_TICKET, SEED_TICKETS)


def init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(CREATE_CUSTOMERS_TABLE)
    cursor.execute(CREATE_TICKETS_TABLE)
    cursor.execute(CREATE_RESPONSES_TABLE)
    _seed_database(cursor)
    conn.commit()
    conn.close()


def _build_search_query(search_term, status, priority, customer_id):
    # NOTE: Query is built by string interpolation, preserved as-is to keep
    # existing behaviour unchanged.
    query = f"""
        SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at, 
               c.name as customer_name, c.email as customer_email
        FROM tickets t
        JOIN customers c ON t.customer_id = c.customer_id
        WHERE (t.subject LIKE '%{search_term}%' OR t.description LIKE '%{search_term}%')
    """
    if status:
        query += f" AND t.status = '{status}'"
    if priority:
        query += f' AND t.priority = {priority}'
    if customer_id:
        query += f" AND t.customer_id = '{customer_id}'"
    return query


@app.route('/tickets/search', methods=['GET'])
async def search_tickets():
    search_term = request.args.get('q', '')
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    customer_id = request.args.get('customer_id', '')

    query = _build_search_query(search_term, status, priority, customer_id)

    with closing(_connect()) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            tickets = [
                dict(zip(TICKET_SEARCH_FIELDS, row))
                for row in cursor.fetchall()
            ]
        except Exception as e:
            error = e
        else:
            error = None

    if error is not None:
        return (await jsonify({'error': str(error)}), 500)
    try:
        return await jsonify({'tickets': tickets})
    except Exception as e:
        return (await jsonify({'error': str(e)}), 500)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    try:
        data = await request.get_json()
        conn = _connect()
        cursor = conn.cursor()
        ticket_id = _generate_id('TICKET')
        cursor.execute(
            INSERT_TICKET,
            (
                ticket_id,
                data['customer_id'],
                data['subject'],
                data['description'],
                data.get('priority', 3),
            ),
        )
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
        response_id = _generate_id('RESP')
        cursor.execute(
            INSERT_RESPONSE,
            (response_id, ticket_id, data['responder'], data['message']),
        )
        conn.commit()
        conn.close()
        return (await jsonify({'response_id': response_id}), 201)
    except Exception as e:
        return (await jsonify({'error': str(e)}), 400)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
