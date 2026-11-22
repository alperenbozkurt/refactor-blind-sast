"""Tornado HTTP API for a small demo bank.

Endpoints:

* ``GET  /account``      -- fetch a single account by ``account_id``.
* ``GET  /transactions`` -- list transactions, optionally filtered by date.
* ``POST /transactions`` -- create a deposit or withdrawal.

State is stored in a local SQLite database (``bank.db``) which is created
and seeded with demo data the first time the application starts.

Run this module directly to start the server on port 8888.
"""

import json
import re
import sqlite3
from datetime import datetime  # noqa: F401  (kept for module-namespace compatibility)

import tornado.ioloop
import tornado.web

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = 'bank.db'
SERVER_PORT = 8888

ROUTE_ACCOUNT = '/account'
ROUTE_TRANSACTIONS = '/transactions'

# HTTP status codes.
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

# Transaction types.
TRANSACTION_TYPE_DEPOSIT = 'deposit'
TRANSACTION_TYPE_WITHDRAWAL = 'withdrawal'
VALID_TRANSACTION_TYPES = (TRANSACTION_TYPE_DEPOSIT, TRANSACTION_TYPE_WITHDRAWAL)

REQUIRED_TRANSACTION_FIELDS = ('account_id', 'amount', 'type')
DEFAULT_TRANSACTION_DESCRIPTION = ''
STATUS_SUCCESS = 'success'

# ``YYYY-MM-DD`` date validation.
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# Client-facing messages.
ERROR_INVALID_ACCOUNT_ID = 'Invalid account ID'
ERROR_INVALID_DATE_FORMAT = 'Invalid date format. Use YYYY-MM-DD'
ERROR_ACCOUNT_NOT_FOUND = 'Account not found'
ERROR_INTERNAL_SERVER = 'Internal server error'
ERROR_MISSING_REQUIRED_FIELDS = 'Missing required fields'
ERROR_INVALID_AMOUNT = 'Invalid amount'
ERROR_AMOUNT_MUST_BE_POSITIVE = 'Amount must be positive'
ERROR_INVALID_TRANSACTION_TYPE = 'Invalid transaction type'
ERROR_INSUFFICIENT_FUNDS = 'Insufficient funds'
ERROR_TRANSACTION_FAILED = 'Transaction failed'

# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

SQL_CREATE_ACCOUNTS_TABLE = """
    CREATE TABLE IF NOT EXISTS accounts (
        account_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        balance REAL DEFAULT 0,
        account_type TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
"""

SQL_CREATE_TRANSACTIONS_TABLE = """
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

SQL_COUNT_ACCOUNTS = 'SELECT COUNT(*) FROM accounts'
SQL_INSERT_ACCOUNT = (
    'INSERT INTO accounts (customer_name, balance, account_type) '
    'VALUES (?, ?, ?)'
)
SQL_INSERT_TRANSACTION = (
    'INSERT INTO transactions (account_id, amount, transaction_type, description) '
    'VALUES (?, ?, ?, ?)'
)
SQL_SELECT_ACCOUNT_BY_ID = 'SELECT * FROM accounts WHERE account_id = ?'
SQL_SELECT_ACCOUNT_EXISTS = 'SELECT 1 FROM accounts WHERE account_id = ?'
SQL_SELECT_ACCOUNT_BALANCE = 'SELECT balance FROM accounts WHERE account_id = ?'
SQL_SELECT_TRANSACTIONS_BY_ACCOUNT = 'SELECT * FROM transactions WHERE account_id = ?'
SQL_FILTER_TRANSACTIONS_START_DATE = ' AND timestamp >= ?'
SQL_FILTER_TRANSACTIONS_END_DATE = ' AND timestamp <= ?'
SQL_INCREMENT_BALANCE = 'UPDATE accounts SET balance = balance + ? WHERE account_id = ?'
SQL_DECREMENT_BALANCE = 'UPDATE accounts SET balance = balance - ? WHERE account_id = ?'

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_ACCOUNTS = (
    ('John Smith', 5000.0, 'checking'),
    ('Alice Johnson', 12000.0, 'savings'),
    ('Bob Williams', 750.0, 'checking'),
)

SEED_TRANSACTIONS = (
    (1, 500.0, TRANSACTION_TYPE_DEPOSIT, 'Initial deposit'),
    (1, -50.0, TRANSACTION_TYPE_WITHDRAWAL, 'ATM withdrawal'),
    (2, 1000.0, TRANSACTION_TYPE_DEPOSIT, 'Paycheck deposit'),
)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def serialize_account(row):
    """Convert an ``accounts`` table row into its JSON representation."""
    account_id, customer_name, balance, account_type, created_at = row
    return {
        'account_id': account_id,
        'customer_name': customer_name,
        'balance': balance,
        'account_type': account_type,
        'created_at': created_at,
    }


def serialize_transaction(row):
    """Convert a ``transactions`` table row into its JSON representation."""
    transaction_id, _account_id, amount, transaction_type, description, timestamp = row
    return {
        'transaction_id': transaction_id,
        'amount': amount,
        'type': transaction_type,
        'description': description,
        'timestamp': timestamp,
    }


# ---------------------------------------------------------------------------
# Application core
# ---------------------------------------------------------------------------

class BankApplication:
    """Owns the database connection plus all persistence and validation logic."""

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    # -- schema management --------------------------------------------------

    def init_db(self):
        cursor = self.conn.cursor()
        self._create_tables(cursor)
        self._seed_if_empty(cursor)
        self.conn.commit()

    def _create_tables(self, cursor):
        cursor.execute(SQL_CREATE_ACCOUNTS_TABLE)
        cursor.execute(SQL_CREATE_TRANSACTIONS_TABLE)

    def _seed_if_empty(self, cursor):
        cursor.execute(SQL_COUNT_ACCOUNTS)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(SQL_INSERT_ACCOUNT, SEED_ACCOUNTS)
            cursor.executemany(SQL_INSERT_TRANSACTION, SEED_TRANSACTIONS)

    # -- validation ---------------------------------------------------------

    def validate_account_id(self, account_id):
        if not account_id or not account_id.isdigit():
            raise ValueError(ERROR_INVALID_ACCOUNT_ID)
        return int(account_id)

    def validate_date(self, date_str):
        if not DATE_PATTERN.match(date_str):
            raise ValueError(ERROR_INVALID_DATE_FORMAT)
        return date_str

    # -- queries ------------------------------------------------------------

    def get_account(self, account_id):
        """Return the raw ``accounts`` row for ``account_id`` or ``None``."""
        cursor = self.conn.cursor()
        cursor.execute(SQL_SELECT_ACCOUNT_BY_ID, (account_id,))
        return cursor.fetchone()

    def get_transactions(self, account_id, start_date=None, end_date=None):
        """Return raw ``transactions`` rows, optionally bounded by dates."""
        cursor = self.conn.cursor()
        query = SQL_SELECT_TRANSACTIONS_BY_ACCOUNT
        params = [account_id]
        if start_date:
            query += SQL_FILTER_TRANSACTIONS_START_DATE
            params.append(start_date)
        if end_date:
            query += SQL_FILTER_TRANSACTIONS_END_DATE
            params.append(end_date)
        cursor.execute(query, params)
        return cursor.fetchall()

    def create_transaction(self, account_id, amount, transaction_type, description):
        """Record a transaction, adjust the balance, and commit.

        Returns the id of the newly created transaction.
        """
        cursor = self.conn.cursor()
        self._require_account(cursor, account_id)
        self._require_sufficient_funds(cursor, account_id, amount, transaction_type)
        cursor.execute(
            SQL_INSERT_TRANSACTION,
            (account_id, amount, transaction_type, description),
        )
        self._apply_balance_change(cursor, account_id, amount, transaction_type)
        self.conn.commit()
        return cursor.lastrowid

    @staticmethod
    def _require_account(cursor, account_id):
        cursor.execute(SQL_SELECT_ACCOUNT_EXISTS, (account_id,))
        if not cursor.fetchone():
            raise ValueError(ERROR_ACCOUNT_NOT_FOUND)

    @staticmethod
    def _require_sufficient_funds(cursor, account_id, amount, transaction_type):
        if transaction_type == TRANSACTION_TYPE_WITHDRAWAL:
            cursor.execute(SQL_SELECT_ACCOUNT_BALANCE, (account_id,))
            balance = cursor.fetchone()[0]
            if balance < amount:
                raise ValueError(ERROR_INSUFFICIENT_FUNDS)

    @staticmethod
    def _apply_balance_change(cursor, account_id, amount, transaction_type):
        if transaction_type == TRANSACTION_TYPE_DEPOSIT:
            cursor.execute(SQL_INCREMENT_BALANCE, (amount, account_id))
        else:
            cursor.execute(SQL_DECREMENT_BALANCE, (amount, account_id))


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

class BaseBankHandler(tornado.web.RequestHandler):
    """Shared wiring for handlers backed by a :class:`BankApplication`."""

    def initialize(self, bank_app):
        self.bank = bank_app

    def write_error_response(self, status_code, message):
        """Write a JSON error body with the given HTTP status code."""
        self.set_status(status_code)
        self.write({'error': message})


class AccountHandler(BaseBankHandler):

    def get(self):
        try:
            account_id = self.bank.validate_account_id(self.get_argument('account_id'))
            account = self.bank.get_account(account_id)
            if account:
                self.write(serialize_account(account))
            else:
                self.write_error_response(HTTP_NOT_FOUND, ERROR_ACCOUNT_NOT_FOUND)
        except ValueError as e:
            self.write_error_response(HTTP_BAD_REQUEST, str(e))
        except Exception:
            self.write_error_response(HTTP_INTERNAL_SERVER_ERROR, ERROR_INTERNAL_SERVER)


class TransactionHandler(BaseBankHandler):

    def get(self):
        try:
            account_id = self.bank.validate_account_id(self.get_argument('account_id'))
            start_date = self.get_argument('start_date', None)
            end_date = self.get_argument('end_date', None)
            if start_date:
                start_date = self.bank.validate_date(start_date)
            if end_date:
                end_date = self.bank.validate_date(end_date)
            rows = self.bank.get_transactions(account_id, start_date, end_date)
            self.write({'transactions': [serialize_transaction(row) for row in rows]})
        except ValueError as e:
            self.write_error_response(HTTP_BAD_REQUEST, str(e))
        except Exception:
            self.write_error_response(HTTP_INTERNAL_SERVER_ERROR, ERROR_INTERNAL_SERVER)

    def post(self):
        try:
            data = json.loads(self.request.body)
            account_id, amount, transaction_type, description = \
                self._parse_transaction_payload(data)
            transaction_id = self.bank.create_transaction(
                account_id, amount, transaction_type, description
            )
            self.write({'status': STATUS_SUCCESS, 'transaction_id': transaction_id})
        except ValueError as e:
            self.write_error_response(HTTP_BAD_REQUEST, str(e))
        except Exception:
            self.bank.conn.rollback()
            self.write_error_response(HTTP_INTERNAL_SERVER_ERROR, ERROR_TRANSACTION_FAILED)

    # -- request parsing ----------------------------------------------------

    def _parse_transaction_payload(self, data):
        """Validate the request body and return normalised transaction fields."""
        if not all(key in data for key in REQUIRED_TRANSACTION_FIELDS):
            raise ValueError(ERROR_MISSING_REQUIRED_FIELDS)
        account_id = self.bank.validate_account_id(str(data['account_id']))
        amount = self._parse_amount(data['amount'])
        transaction_type = data['type']
        if transaction_type not in VALID_TRANSACTION_TYPES:
            raise ValueError(ERROR_INVALID_TRANSACTION_TYPE)
        description = data.get('description', DEFAULT_TRANSACTION_DESCRIPTION)
        return account_id, amount, transaction_type, description

    @staticmethod
    def _parse_amount(raw_amount):
        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError(ERROR_AMOUNT_MUST_BE_POSITIVE)
        except ValueError:
            # All amount problems (including non-positive values) are
            # normalised to a single client-facing message.
            raise ValueError(ERROR_INVALID_AMOUNT)
        return amount


# ---------------------------------------------------------------------------
# Application factory & entry point
# ---------------------------------------------------------------------------

def make_app():
    bank_app = BankApplication()
    return tornado.web.Application([
        (ROUTE_ACCOUNT, AccountHandler, dict(bank_app=bank_app)),
        (ROUTE_TRANSACTIONS, TransactionHandler, dict(bank_app=bank_app)),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
