import tornado.ioloop
import tornado.web
import sqlite3
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DATABASE_PATH = 'bank.db'
SERVER_PORT = 8888

ACCOUNT_ROUTE = '/account'
TRANSACTIONS_ROUTE = '/transactions'

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

TRANSACTION_TYPE_DEPOSIT = 'deposit'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_ACCOUNTS_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS accounts (
        account_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        balance REAL DEFAULT 0,
        account_type TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
'''

CREATE_TRANSACTIONS_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        transaction_type TEXT NOT NULL,
        description TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(account_id)
    )
'''

COUNT_ACCOUNTS_SQL = 'SELECT COUNT(*) FROM accounts'

INSERT_ACCOUNT_SQL = '''
    INSERT INTO accounts (customer_name, balance, account_type)
    VALUES (?, ?, ?)
'''

INSERT_TRANSACTION_SQL = '''
    INSERT INTO transactions (account_id, amount, transaction_type, description)
    VALUES (?, ?, ?, ?)
'''

CREDIT_ACCOUNT_SQL = '''
    UPDATE accounts SET balance = balance + ? WHERE account_id = ?
'''

DEBIT_ACCOUNT_SQL = '''
    UPDATE accounts SET balance = balance - ? WHERE account_id = ?
'''

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_ACCOUNTS = [
    ('John Smith', 5000.0, 'checking'),
    ('Alice Johnson', 12000.0, 'savings'),
    ('Bob Williams', 750.0, 'checking'),
]

SEED_TRANSACTIONS = [
    (1, 500.0, 'deposit', 'Initial deposit'),
    (1, -50.0, 'withdrawal', 'ATM withdrawal'),
    (2, 1000.0, 'deposit', 'Paycheck deposit'),
]


# ---------------------------------------------------------------------------
# Query builders / row serializers
# ---------------------------------------------------------------------------
# NOTE: these builders intentionally preserve the original query-construction
# behavior (values interpolated into the SQL text) so that responses are
# identical to the previous implementation.

def build_account_query(account_id):
    return f'SELECT * FROM accounts WHERE account_id = {account_id}'


def build_transactions_query(account_id, start_date=None, end_date=None):
    query = f'SELECT * FROM transactions WHERE account_id = {account_id}'
    if start_date:
        query += f" AND timestamp >= '{start_date}'"
    if end_date:
        query += f" AND timestamp <= '{end_date}'"
    return query


def account_row_to_dict(row):
    return {
        'account_id': row[0],
        'customer_name': row[1],
        'balance': row[2],
        'account_type': row[3],
        'created_at': row[4],
    }


def transaction_row_to_dict(row):
    return {
        'transaction_id': row[0],
        'amount': row[2],
        'type': row[3],
        'description': row[4],
        'timestamp': row[5],
    }


# ---------------------------------------------------------------------------
# Application / persistence
# ---------------------------------------------------------------------------

class BankApplication:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        self._create_tables(cursor)
        if self._accounts_table_is_empty(cursor):
            self._seed_data(cursor)
        self.conn.commit()

    @staticmethod
    def _create_tables(cursor):
        cursor.execute(CREATE_ACCOUNTS_TABLE_SQL)
        cursor.execute(CREATE_TRANSACTIONS_TABLE_SQL)

    @staticmethod
    def _accounts_table_is_empty(cursor):
        cursor.execute(COUNT_ACCOUNTS_SQL)
        return cursor.fetchone()[0] == 0

    @staticmethod
    def _seed_data(cursor):
        cursor.executemany(INSERT_ACCOUNT_SQL, SEED_ACCOUNTS)
        cursor.executemany(INSERT_TRANSACTION_SQL, SEED_TRANSACTIONS)


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

class BankRequestHandler(tornado.web.RequestHandler):
    """Base handler providing access to the bank application and error helpers."""

    def initialize(self, bank_app):
        self.bank = bank_app

    def write_error_response(self, status, error):
        self.set_status(status)
        self.write({'error': str(error)})


class AccountHandler(BankRequestHandler):

    def get(self):
        account_id = self.get_argument('account_id')
        cursor = self.bank.conn.cursor()
        query = build_account_query(account_id)
        try:
            cursor.execute(query)
            account = cursor.fetchone()
            if account:
                self.write(account_row_to_dict(account))
            else:
                self.set_status(HTTP_NOT_FOUND)
                self.write({'error': 'Account not found'})
        except Exception as e:
            self.write_error_response(HTTP_INTERNAL_SERVER_ERROR, e)


class TransactionHandler(BankRequestHandler):

    def get(self):
        account_id = self.get_argument('account_id')
        start_date = self.get_argument('start_date', None)
        end_date = self.get_argument('end_date', None)
        cursor = self.bank.conn.cursor()
        query = build_transactions_query(account_id, start_date, end_date)
        try:
            cursor.execute(query)
            transactions = [transaction_row_to_dict(row) for row in cursor.fetchall()]
            self.write({'transactions': transactions})
        except Exception as e:
            self.write_error_response(HTTP_INTERNAL_SERVER_ERROR, e)

    def post(self):
        try:
            data = json.loads(self.request.body)
            cursor = self.bank.conn.cursor()
            cursor.execute(
                INSERT_TRANSACTION_SQL,
                (data['account_id'], data['amount'], data['type'], data.get('description', '')),
            )
            self._apply_balance_change(cursor, data)
            self.bank.conn.commit()
            self.write({'status': 'success', 'transaction_id': cursor.lastrowid})
        except Exception as e:
            self.write_error_response(HTTP_BAD_REQUEST, e)

    @staticmethod
    def _apply_balance_change(cursor, data):
        if data['type'] == TRANSACTION_TYPE_DEPOSIT:
            sql = CREDIT_ACCOUNT_SQL
        else:
            sql = DEBIT_ACCOUNT_SQL
        cursor.execute(sql, (data['amount'], data['account_id']))


# ---------------------------------------------------------------------------
# Application factory / entry point
# ---------------------------------------------------------------------------

def make_app():
    bank_app = BankApplication()
    return tornado.web.Application([
        (ACCOUNT_ROUTE, AccountHandler, dict(bank_app=bank_app)),
        (TRANSACTIONS_ROUTE, TransactionHandler, dict(bank_app=bank_app)),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
