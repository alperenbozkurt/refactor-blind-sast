import sqlite3
import uuid
from contextlib import closing
from datetime import datetime  # noqa: F401  (kept for module-level name compatibility)

from quart import Quart, request, jsonify

app = Quart(__name__)


# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
class Config:
    DATABASE_PATH = 'support.db'
    HOST = '0.0.0.0'
    PORT = 8000

    TICKET_ID_PREFIX = 'TICKET'
    RESPONSE_ID_PREFIX = 'RESP'
    ID_SUFFIX_LENGTH = 4

    DEFAULT_PRIORITY = 3

    HTTP_CREATED = 201
    HTTP_BAD_REQUEST = 400
    HTTP_SERVER_ERROR = 500


DB_PATH = Config.DATABASE_PATH

CREATE_CUSTOMERS_TABLE = '''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    '''

CREATE_TICKETS_TABLE = '''
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

CREATE_RESPONSES_TABLE = '''
        CREATE TABLE IF NOT EXISTS responses (
            response_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            responder TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
        )
    '''

SCHEMA_STATEMENTS = (
    CREATE_CUSTOMERS_TABLE,
    CREATE_TICKETS_TABLE,
    CREATE_RESPONSES_TABLE,
)

COUNT_CUSTOMERS = 'SELECT COUNT(*) FROM customers'

INSERT_CUSTOMER = '''
            INSERT INTO customers (customer_id, name, email, phone)
            VALUES (?, ?, ?, ?)
        '''

INSERT_SEED_TICKET = '''
            INSERT INTO tickets (ticket_id, customer_id, subject, description, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        '''

INSERT_TICKET = '''
            INSERT INTO tickets (ticket_id, customer_id, subject, description, priority)
            VALUES (?, ?, ?, ?, ?)
        '''

INSERT_RESPONSE = '''
            INSERT INTO responses (response_id, ticket_id, responder, message)
            VALUES (?, ?, ?, ?)
        '''

SEARCH_BASE_QUERY = '''
        SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at, 
               c.name as customer_name, c.email as customer_email
        FROM tickets t
        JOIN customers c ON t.customer_id = c.customer_id
        WHERE (t.subject LIKE ? OR t.description LIKE ?)
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

SEARCH_RESULT_FIELDS = (
    'ticket_id',
    'subject',
    'status',
    'priority',
    'created_at',
    'customer_name',
    'customer_email',
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _connect():
    """Open a new connection to the support database."""
    return sqlite3.connect(DB_PATH)


def _generate_id(prefix):
    """Generate a short, prefixed, upper-case identifier."""
    suffix = str(uuid.uuid4())[:Config.ID_SUFFIX_LENGTH].upper()
    return f'{prefix}-{suffix}'


def _seed_database(cursor):
    """Populate an empty database with sample data."""
    cursor.execute(COUNT_CUSTOMERS)
    if cursor.fetchone()[0] == 0:
        cursor.executemany(INSERT_CUSTOMER, SEED_CUSTOMERS)
        cursor.executemany(INSERT_SEED_TICKET, SEED_TICKETS)


def _build_search_query(search_term, status, priority, customer_id):
    """Build the (parameterised) ticket search query and its parameters."""
    pattern = f'%{search_term}%'
    query = SEARCH_BASE_QUERY
    params = [pattern, pattern]
    if status:
        query += ' AND t.status = ?'
        params.append(status)
    if priority:
        query += ' AND t.priority = ?'
        params.append(priority)
    if customer_id:
        query += ' AND t.customer_id = ?'
        params.append(customer_id)
    return query, params


def _row_to_ticket(row):
    """Convert a search result row into a JSON-serialisable dict."""
    return dict(zip(SEARCH_RESULT_FIELDS, row))


def _insert_and_commit(sql, params):
    """Execute a single write statement and commit it."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()


# --------------------------------------------------------------------------- #
# Database initialisation
# --------------------------------------------------------------------------- #
def init_db():
    conn = _connect()
    cursor = conn.cursor()
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)
    _seed_database(cursor)
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/tickets/search', methods=['GET'])
async def search_tickets():
    search_term = request.args.get('q', '')
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    customer_id = request.args.get('customer_id', '')

    conn = _connect()
    cursor = conn.cursor()
    query, params = _build_search_query(search_term, status, priority, customer_id)
    try:
        cursor.execute(query, params)
        tickets = [_row_to_ticket(row) for row in cursor.fetchall()]
        conn.close()
        return await jsonify({'tickets': tickets})
    except Exception as e:
        conn.close()
        return (await jsonify({'error': str(e)}), Config.HTTP_SERVER_ERROR)


@app.route('/tickets/create', methods=['POST'])
async def create_ticket():
    try:
        data = await request.get_json()
        ticket_id = _generate_id(Config.TICKET_ID_PREFIX)
        _insert_and_commit(
            INSERT_TICKET,
            (
                ticket_id,
                data['customer_id'],
                data['subject'],
                data['description'],
                data.get('priority', Config.DEFAULT_PRIORITY),
            ),
        )
        return (await jsonify({'ticket_id': ticket_id}), Config.HTTP_CREATED)
    except Exception as e:
        return (await jsonify({'error': str(e)}), Config.HTTP_BAD_REQUEST)


@app.route('/tickets/<ticket_id>/respond', methods=['POST'])
async def add_response(ticket_id):
    try:
        data = await request.get_json()
        response_id = _generate_id(Config.RESPONSE_ID_PREFIX)
        _insert_and_commit(
            INSERT_RESPONSE,
            (response_id, ticket_id, data['responder'], data['message']),
        )
        return (await jsonify({'response_id': response_id}), Config.HTTP_CREATED)
    except Exception as e:
        return (await jsonify({'error': str(e)}), Config.HTTP_BAD_REQUEST)


if __name__ == '__main__':
    init_db()
    app.run(host=Config.HOST, port=Config.PORT)
