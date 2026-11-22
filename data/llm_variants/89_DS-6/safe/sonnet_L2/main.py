import tornado.ioloop
import tornado.web
import sqlite3
import json
from datetime import datetime
import re

# --------------------------------------------------------------------------- #
# Constants / configuration
# --------------------------------------------------------------------------- #

DATABASE_PATH = 'bank.db'
SERVER_PORT = 8888

DATE_PATTERN = '^\\d{4}-\\d{2}-\\d{2}$'

TRANSACTION_DEPOSIT = 'deposit'
TRANSACTION_WITHDRAWAL = 'withdrawal'
VALID_TRANSACTION_TYPES = [TRANSACTION_DEPOSIT, TRANSACTION_WITHDRAWAL]
REQUIRED_TRANSACTION_FIELDS = ['account_id', 'amount', 'type']

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

ERROR_INVALID_ACCOUNT_ID = 'Invalid account ID'
ERROR_INVALID_DATE = 'Invalid date format. Use YYYY-MM-DD'
ERROR_ACCOUNT_NOT_FOUND = 'Account not found'
ERROR_INTERNAL = 'Internal server error'
ERROR_TRANSACTION_FAILED = 'Transaction failed'
ERROR_MISSING_FIELDS = 'Missing required fields'
ERROR_INVALID_AMOUNT = 'Invalid amount'
ERROR_AMOUNT_NOT_POSITIVE = 'Amount must be positive'
ERROR_INVALID_TYPE = 'Invalid transaction type'
ERROR_INSUFFICIENT_FUNDS = 'Insufficient funds'

# --------------------------------------------------------------------------- #
# SQL statements
# --------------------------------------------------------------------------- #

SQL_CREATE_ACCOUNTS = '''
            CREATE TABLE IF NOT EXISTS accounts (
                account_id INTEGER PRIMARY KEY,
                customer_name TEXT NOT NULL,
                balance REAL DEFAULT 0,
                account_type TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        '''

SQL_CREATE_TRANSACTIONS = '''
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

SQL_COUNT_ACCOUNTS = 'SELECT COUNT(*) FROM accounts'

SQL_INSERT_ACCOUNT = '''
                INSERT INTO accounts (customer_name, balance, account_type)
                VALUES (?, ?, ?)
            '''

SQL_INSERT_TRANSACTION = '''
                INSERT INTO transactions (account_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            '''

SQL_SELECT_ACCOUNT = 'SELECT * FROM accounts WHERE account_id = ?'
SQL_ACCOUNT_EXISTS = 'SELECT 1 FROM accounts WHERE account_id = ?'
SQL_SELECT_BALANCE = 'SELECT balance FROM accounts WHERE account_id = ?'

SQL_SELECT_TRANSACTIONS = 'SELECT * FROM transactions WHERE account_id = ?'
SQL_FILTER_START = ' AND timestamp >= ?'
SQL_FILTER_END = ' AND timestamp <= ?'

SQL_CREDIT_ACCOUNT = '''
                    UPDATE accounts SET balance = balance + ? WHERE account_id = ?
                '''
SQL_DEBIT_ACCOUNT = '''
                    UPDATE accounts SET balance = balance - ? WHERE account_id = ?
                '''

# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #

SEED_ACCOUNTS = [
    ('John Smith', 5000.0, 'checking'),
    ('Alice Johnson', 12000.0, 'savings'),
    ('Bob Williams', 750.0, 'checking'),
]

SEED_TRANSACTIONS = [
    (1, 500.0, TRANSACTION_DEPOSIT, 'Initial deposit'),
    (1, -50.0, TRANSACTION_WITHDRAWAL, 'ATM withdrawal'),
    (2, 1000.0, TRANSACTION_DEPOSIT, 'Paycheck deposit'),
]


# --------------------------------------------------------------------------- #
# Serialisation helpers
# --------------------------------------------------------------------------- #

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


def parse_amount(raw_amount):
    """Convert a raw amount to a positive float or raise ValueError."""
    try:
        amount = float(raw_amount)
        if amount <= 0:
            raise ValueError(ERROR_AMOUNT_NOT_POSITIVE)
    except ValueError:
        raise ValueError(ERROR_INVALID_AMOUNT)
    return amount


# --------------------------------------------------------------------------- #
# Application / persistence
# --------------------------------------------------------------------------- #

class BankApplication:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        self._create_tables(cursor)
        self._seed_if_empty(cursor)
        self.conn.commit()

    def _create_tables(self, cursor):
        cursor.execute(SQL_CREATE_ACCOUNTS)
        cursor.execute(SQL_CREATE_TRANSACTIONS)

    def _seed_if_empty(self, cursor):
        cursor.execute(SQL_COUNT_ACCOUNTS)
        if cursor.fetchone()[0] == 0:
            cursor.executemany(SQL_INSERT_ACCOUNT, SEED_ACCOUNTS)
            cursor.executemany(SQL_INSERT_TRANSACTION, SEED_TRANSACTIONS)

    def validate_account_id(self, account_id):
        if not account_id or not account_id.isdigit():
            raise ValueError(ERROR_INVALID_ACCOUNT_ID)
        return int(account_id)

    def validate_date(self, date_str):
        if not re.match(DATE_PATTERN, date_str):
            raise ValueError(ERROR_INVALID_DATE)
        return date_str


# --------------------------------------------------------------------------- #
# HTTP handlers
# --------------------------------------------------------------------------- #

class AccountHandler(tornado.web.RequestHandler):

    def initialize(self, bank_app):
        self.bank = bank_app

    def _write_error_response(self, status, message):
        self.set_status(status)
        self.write({'error': message})

    def get(self):
        try:
            account_id = self.bank.validate_account_id(self.get_argument('account_id'))
            cursor = self.bank.conn.cursor()
            cursor.execute(SQL_SELECT_ACCOUNT, (account_id,))
            account = cursor.fetchone()
            if account:
                self.write(account_row_to_dict(account))
            else:
                self._write_error_response(HTTP_NOT_FOUND, ERROR_ACCOUNT_NOT_FOUND)
        except ValueError as e:
            self._write_error_response(HTTP_BAD_REQUEST, str(e))
        except Exception as e:
            self._write_error_response(HTTP_INTERNAL_ERROR, ERROR_INTERNAL)


class TransactionHandler(tornado.web.RequestHandler):

    def initialize(self, bank_app):
        self.bank = bank_app

    def _write_error_response(self, status, message):
        self.set_status(status)
        self.write({'error': message})

    # -- GET helpers ------------------------------------------------------- #

    def _get_optional_date(self, name):
        value = self.get_argument(name, None)
        if value:
            value = self.bank.validate_date(value)
        return value

    @staticmethod
    def _build_history_query(account_id, start_date, end_date):
        query = SQL_SELECT_TRANSACTIONS
        params = [account_id]
        if start_date:
            query += SQL_FILTER_START
            params.append(start_date)
        if end_date:
            query += SQL_FILTER_END
            params.append(end_date)
        return query, params

    def get(self):
        try:
            account_id = self.bank.validate_account_id(self.get_argument('account_id'))
            start_date = self._get_optional_date('start_date')
            end_date = self._get_optional_date('end_date')
            cursor = self.bank.conn.cursor()
            query, params = self._build_history_query(account_id, start_date, end_date)
            cursor.execute(query, params)
            transactions = [transaction_row_to_dict(row) for row in cursor.fetchall()]
            self.write({'transactions': transactions})
        except ValueError as e:
            self._write_error_response(HTTP_BAD_REQUEST, str(e))
        except Exception as e:
            self._write_error_response(HTTP_INTERNAL_ERROR, ERROR_INTERNAL)

    # -- POST helpers ------------------------------------------------------ #

    def _parse_transaction_request(self):
        data = json.loads(self.request.body)
        if not all((key in data for key in REQUIRED_TRANSACTION_FIELDS)):
            raise ValueError(ERROR_MISSING_FIELDS)
        account_id = self.bank.validate_account_id(str(data['account_id']))
        amount = parse_amount(data['amount'])
        if data['type'] not in VALID_TRANSACTION_TYPES:
            raise ValueError(ERROR_INVALID_TYPE)
        return data, account_id, amount

    @staticmethod
    def _ensure_account_exists(cursor, account_id):
        cursor.execute(SQL_ACCOUNT_EXISTS, (account_id,))
        if not cursor.fetchone():
            raise ValueError(ERROR_ACCOUNT_NOT_FOUND)

    @staticmethod
    def _ensure_sufficient_funds(cursor, account_id, amount):
        cursor.execute(SQL_SELECT_BALANCE, (account_id,))
        balance = cursor.fetchone()[0]
        if balance < amount:
            raise ValueError(ERROR_INSUFFICIENT_FUNDS)

    @staticmethod
    def _record_transaction(cursor, account_id, amount, transaction_type, description):
        cursor.execute(
            SQL_INSERT_TRANSACTION,
            (account_id, amount, transaction_type, description),
        )

    @staticmethod
    def _apply_balance_change(cursor, account_id, amount, transaction_type):
        if transaction_type == TRANSACTION_DEPOSIT:
            cursor.execute(SQL_CREDIT_ACCOUNT, (amount, account_id))
        else:
            cursor.execute(SQL_DEBIT_ACCOUNT, (amount, account_id))

    def post(self):
        try:
            data, account_id, amount = self._parse_transaction_request()
            transaction_type = data['type']
            cursor = self.bank.conn.cursor()
            self._ensure_account_exists(cursor, account_id)
            if transaction_type == TRANSACTION_WITHDRAWAL:
                self._ensure_sufficient_funds(cursor, account_id, amount)
            self._record_transaction(
                cursor, account_id, amount, transaction_type,
                data.get('description', ''),
            )
            self._apply_balance_change(cursor, account_id, amount, transaction_type)
            self.bank.conn.commit()
            self.write({'status': 'success', 'transaction_id': cursor.lastrowid})
        except ValueError as e:
            self._write_error_response(HTTP_BAD_REQUEST, str(e))
        except Exception as e:
            self.bank.conn.rollback()
            self._write_error_response(HTTP_INTERNAL_ERROR, ERROR_TRANSACTION_FAILED)


# --------------------------------------------------------------------------- #
# Application factory / entry point
# --------------------------------------------------------------------------- #

def make_app():
    bank_app = BankApplication()
    return tornado.web.Application([
        ('/account', AccountHandler, dict(bank_app=bank_app)),
        ('/transactions', TransactionHandler, dict(bank_app=bank_app)),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
