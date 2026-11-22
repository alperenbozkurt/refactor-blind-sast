import tornado.ioloop
import tornado.web
import sqlite3
import json
from datetime import datetime
import re

DATABASE_PATH = 'bank.db'

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

INSERT_ACCOUNT_SQL = '''
    INSERT INTO accounts (customer_name, balance, account_type)
    VALUES (?, ?, ?)
'''

INSERT_TRANSACTION_SQL = '''
    INSERT INTO transactions (account_id, amount, transaction_type, description)
    VALUES (?, ?, ?, ?)
'''

SEED_ACCOUNTS = (
    ('John Smith', 5000.0, 'checking'),
    ('Alice Johnson', 12000.0, 'savings'),
    ('Bob Williams', 750.0, 'checking'),
)

SEED_TRANSACTIONS = (
    (1, 500.0, 'deposit', 'Initial deposit'),
    (1, -50.0, 'withdrawal', 'ATM withdrawal'),
    (2, 1000.0, 'deposit', 'Paycheck deposit'),
)

DATE_FORMAT_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

TRANSACTION_TYPES = ('deposit', 'withdrawal')
REQUIRED_TRANSACTION_FIELDS = ('account_id', 'amount', 'type')


class BankApplication:

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_ACCOUNTS_TABLE_SQL)
        cursor.execute(CREATE_TRANSACTIONS_TABLE_SQL)
        if self._accounts_table_is_empty(cursor):
            self._seed_data(cursor)
        self.conn.commit()

    @staticmethod
    def _accounts_table_is_empty(cursor):
        cursor.execute('SELECT COUNT(*) FROM accounts')
        return cursor.fetchone()[0] == 0

    @staticmethod
    def _seed_data(cursor):
        cursor.executemany(INSERT_ACCOUNT_SQL, SEED_ACCOUNTS)
        cursor.executemany(INSERT_TRANSACTION_SQL, SEED_TRANSACTIONS)

    def validate_account_id(self, account_id):
        if not account_id or not account_id.isdigit():
            raise ValueError('Invalid account ID')
        return int(account_id)

    def validate_date(self, date_str):
        if not DATE_FORMAT_PATTERN.match(date_str):
            raise ValueError('Invalid date format. Use YYYY-MM-DD')
        return date_str


class BankRequestHandler(tornado.web.RequestHandler):

    def initialize(self, bank_app):
        self.bank = bank_app

    def write_api_error(self, status_code, message):
        self.set_status(status_code)
        self.write({'error': message})


class AccountHandler(BankRequestHandler):

    def get(self):
        try:
            account_id = self.bank.validate_account_id(
                self.get_argument('account_id'))
            account = self._fetch_account(account_id)
            if account:
                self.write(self._serialize_account(account))
            else:
                self.write_api_error(404, 'Account not found')
        except ValueError as e:
            self.write_api_error(400, str(e))
        except Exception:
            self.write_api_error(500, 'Internal server error')

    def _fetch_account(self, account_id):
        cursor = self.bank.conn.cursor()
        cursor.execute(
            'SELECT * FROM accounts WHERE account_id = ?', (account_id,))
        return cursor.fetchone()

    @staticmethod
    def _serialize_account(row):
        return {
            'account_id': row[0],
            'customer_name': row[1],
            'balance': row[2],
            'account_type': row[3],
            'created_at': row[4],
        }


class TransactionHandler(BankRequestHandler):

    def get(self):
        try:
            account_id = self.bank.validate_account_id(
                self.get_argument('account_id'))
            start_date = self._get_validated_date('start_date')
            end_date = self._get_validated_date('end_date')
            rows = self._fetch_transactions(account_id, start_date, end_date)
            transactions = [self._serialize_transaction(row) for row in rows]
            self.write({'transactions': transactions})
        except ValueError as e:
            self.write_api_error(400, str(e))
        except Exception:
            self.write_api_error(500, 'Internal server error')

    def post(self):
        try:
            data = json.loads(self.request.body)
            account_id, amount, txn_type, description = \
                self._parse_transaction(data)
            transaction_id = self._record_transaction(
                account_id, amount, txn_type, description)
            self.write({'status': 'success', 'transaction_id': transaction_id})
        except ValueError as e:
            self.write_api_error(400, str(e))
        except Exception:
            self.bank.conn.rollback()
            self.write_api_error(500, 'Transaction failed')

    def _get_validated_date(self, argument_name):
        date_str = self.get_argument(argument_name, None)
        if date_str:
            date_str = self.bank.validate_date(date_str)
        return date_str

    def _fetch_transactions(self, account_id, start_date, end_date):
        query = 'SELECT * FROM transactions WHERE account_id = ?'
        params = [account_id]
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        cursor = self.bank.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    @staticmethod
    def _serialize_transaction(row):
        return {
            'transaction_id': row[0],
            'amount': row[2],
            'type': row[3],
            'description': row[4],
            'timestamp': row[5],
        }

    def _parse_transaction(self, data):
        if not all(field in data for field in REQUIRED_TRANSACTION_FIELDS):
            raise ValueError('Missing required fields')
        account_id = self.bank.validate_account_id(str(data['account_id']))
        amount = self._parse_amount(data['amount'])
        if data['type'] not in TRANSACTION_TYPES:
            raise ValueError('Invalid transaction type')
        return account_id, amount, data['type'], data.get('description', '')

    @staticmethod
    def _parse_amount(value):
        try:
            amount = float(value)
            if amount <= 0:
                raise ValueError('Amount must be positive')
        except ValueError:
            raise ValueError('Invalid amount')
        return amount

    def _record_transaction(self, account_id, amount, txn_type, description):
        cursor = self.bank.conn.cursor()
        if not self._account_exists(cursor, account_id):
            raise ValueError('Account not found')
        if txn_type == 'withdrawal':
            self._ensure_sufficient_funds(cursor, account_id, amount)
        cursor.execute(
            INSERT_TRANSACTION_SQL, (account_id, amount, txn_type, description))
        self._update_balance(cursor, account_id, amount, txn_type)
        self.bank.conn.commit()
        return cursor.lastrowid

    @staticmethod
    def _account_exists(cursor, account_id):
        cursor.execute(
            'SELECT 1 FROM accounts WHERE account_id = ?', (account_id,))
        return cursor.fetchone() is not None

    @staticmethod
    def _ensure_sufficient_funds(cursor, account_id, amount):
        cursor.execute(
            'SELECT balance FROM accounts WHERE account_id = ?', (account_id,))
        balance = cursor.fetchone()[0]
        if balance < amount:
            raise ValueError('Insufficient funds')

    @staticmethod
    def _update_balance(cursor, account_id, amount, txn_type):
        delta = amount if txn_type == 'deposit' else -amount
        cursor.execute(
            'UPDATE accounts SET balance = balance + ? WHERE account_id = ?',
            (delta, account_id))


def make_app():
    bank_app = BankApplication()
    return tornado.web.Application([
        ('/account', AccountHandler, dict(bank_app=bank_app)),
        ('/transactions', TransactionHandler, dict(bank_app=bank_app)),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
