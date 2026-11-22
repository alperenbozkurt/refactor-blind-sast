"""SQLite-backed Tornado banking API.

The module is organised into small, single-purpose pieces -- configuration
constants, SQL statements, seed data, row serializers, query builders and
database helpers -- which keep the request handlers thin and make each
part easy to test and reuse in a larger codebase.
"""

import json
import sqlite3
from datetime import datetime  # kept to preserve the module's public names

import tornado.ioloop
import tornado.web

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'bank.db'
SERVER_PORT = 8888

ACCOUNT_ROUTE = '/account'
TRANSACTIONS_ROUTE = '/transactions'

TRANSACTION_TYPE_DEPOSIT = 'deposit'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

CREATE_ACCOUNTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS accounts (
        account_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        balance REAL DEFAULT 0,
        account_type TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_TRANSACTIONS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        transaction_type TEXT NOT NULL,
        description TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(account_id)
    )
"""

COUNT_ACCOUNTS_SQL = 'SELECT COUNT(*) FROM accounts'

INSERT_ACCOUNT_SQL = """
    INSERT INTO accounts (customer_name, balance, account_type)
    VALUES (?, ?, ?)
"""

INSERT_TRANSACTION_SQL = """
    INSERT INTO transactions (account_id, amount, transaction_type, description)
    VALUES (?, ?, ?, ?)
"""

INCREASE_BALANCE_SQL = """
    UPDATE accounts SET balance = balance + ? WHERE account_id = ?
"""

DECREASE_BALANCE_SQL = """
    UPDATE accounts SET balance = balance - ? WHERE account_id = ?
"""

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
# Serializers
# ---------------------------------------------------------------------------

def account_to_dict(row):
    """Serialize a row from the accounts table into a JSON-friendly dict."""
    return {
        'account_id': row[0],
        'customer_name': row[1],
        'balance': row[2],
        'account_type': row[3],
        'created_at': row[4],
    }


def transaction_to_dict(row):
    """Serialize a row from the transactions table into a JSON-friendly dict."""
    return {
        'transaction_id': row[0],
        'amount': row[2],
        'type': row[3],
        'description': row[4],
        'timestamp': row[5],
    }


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

def build_account_query(account_id):
    return f'SELECT * FROM accounts WHERE account_id = {account_id}'


def build_transactions_query(account_id, start_date=None, end_date=None):
    query = f'SELECT * FROM transactions WHERE account_id = {account_id}'
    if start_date:
        query += f" AND timestamp >= '{start_date}'"
    if end_date:
        query += f" AND timestamp <= '{end_date}'"
    return query


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def insert_transaction(cursor, data):
    cursor.execute(
        INSERT_TRANSACTION_SQL,
        (data['account_id'], data['amount'], data['type'], data.get('description', '')),
    )


def update_account_balance(cursor, data):
    if data['type'] == TRANSACTION_TYPE_DEPOSIT:
        cursor.execute(INCREASE_BALANCE_SQL, (data['amount'], data['account_id']))
    else:
        cursor.execute(DECREASE_BALANCE_SQL, (data['amount'], data['account_id']))


def write_error_response(handler, status_code, error):
    handler.set_status(status_code)
    handler.write({'error': str(error)})


class BankApplication:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        self._create_tables(cursor)
        self._seed_database_if_empty(cursor)
        self.conn.commit()

    def _create_tables(self, cursor):
        cursor.execute(CREATE_ACCOUNTS_TABLE_SQL)
        cursor.execute(CREATE_TRANSACTIONS_TABLE_SQL)

    def _seed_database_if_empty(self, cursor):
        cursor.execute(COUNT_ACCOUNTS_SQL)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_ACCOUNT_SQL, SEED_ACCOUNTS)
            cursor.executemany(INSERT_TRANSACTION_SQL, SEED_TRANSACTIONS)


class AccountHandler(tornado.web.RequestHandler):

    def initialize(self, bank_app):
        self.bank = bank_app

    def get(self):
        account_id = self.get_argument('account_id')
        cursor = self.bank.conn.cursor()
        query = build_account_query(account_id)
        try:
            cursor.execute(query)
            account = cursor.fetchone()
            if account:
                self.write(account_to_dict(account))
            else:
                write_error_response(self, 404, 'Account not found')
        except Exception as e:
            write_error_response(self, 500, e)


class TransactionHandler(tornado.web.RequestHandler):

    def initialize(self, bank_app):
        self.bank = bank_app

    def get(self):
        account_id = self.get_argument('account_id')
        start_date = self.get_argument('start_date', None)
        end_date = self.get_argument('end_date', None)
        cursor = self.bank.conn.cursor()
        query = build_transactions_query(account_id, start_date, end_date)
        try:
            cursor.execute(query)
            transactions = [transaction_to_dict(row) for row in cursor.fetchall()]
            self.write({'transactions': transactions})
        except Exception as e:
            write_error_response(self, 500, e)

    def post(self):
        try:
            data = json.loads(self.request.body)
            cursor = self.bank.conn.cursor()
            insert_transaction(cursor, data)
            update_account_balance(cursor, data)
            self.bank.conn.commit()
            self.write({'status': 'success', 'transaction_id': cursor.lastrowid})
        except Exception as e:
            write_error_response(self, 400, e)


def make_app():
    bank_app = BankApplication()
    return tornado.web.Application([
        (ACCOUNT_ROUTE, AccountHandler, dict(bank_app=bank_app)),
        (TRANSACTIONS_ROUTE, TransactionHandler, dict(bank_app=bank_app)),
    ])


def main():
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
