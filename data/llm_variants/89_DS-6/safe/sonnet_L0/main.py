import tornado.ioloop
import tornado.web
import sqlite3
import json
from datetime import datetime
import re

DB_PATH = 'bank.db'
DATE_PATTERN = '^\\d{4}-\\d{2}-\\d{2}$'
REQUIRED_TRANSACTION_FIELDS = ('account_id', 'amount', 'type')
TRANSACTION_TYPES = ('deposit', 'withdrawal')

CREATE_ACCOUNTS_SQL = """
    CREATE TABLE IF NOT EXISTS accounts (
        account_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        balance REAL DEFAULT 0,
        account_type TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_TRANSACTIONS_SQL = """
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

INSERT_ACCOUNT_SQL = """
    INSERT INTO accounts (customer_name, balance, account_type)
    VALUES (?, ?, ?)
"""

INSERT_TRANSACTION_SQL = """
    INSERT INTO transactions (account_id, amount, transaction_type, description)
    VALUES (?, ?, ?, ?)
"""

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

BALANCE_UPDATE_SQL = {
    'deposit': 'UPDATE accounts SET balance = balance + ? WHERE account_id = ?',
    'withdrawal': 'UPDATE accounts SET balance = balance - ? WHERE account_id = ?',
}


class BankApplication:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_ACCOUNTS_SQL)
        cursor.execute(CREATE_TRANSACTIONS_SQL)
        cursor.execute('SELECT COUNT(*) FROM accounts')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(INSERT_ACCOUNT_SQL, SEED_ACCOUNTS)
            cursor.executemany(INSERT_TRANSACTION_SQL, SEED_TRANSACTIONS)
        self.conn.commit()

    def validate_account_id(self, account_id):
        if not account_id or not account_id.isdigit():
            raise ValueError('Invalid account ID')
        return int(account_id)

    def validate_date(self, date_str):
        if not re.match(DATE_PATTERN, date_str):
            raise ValueError('Invalid date format. Use YYYY-MM-DD')
        return date_str


class BaseBankHandler(tornado.web.RequestHandler):

    def initialize(self, bank_app):
        self.bank = bank_app

    def write_error_response(self, status, message):
        self.set_status(status)
        self.write({'error': message})


class AccountHandler(BaseBankHandler):

    def get(self):
        try:
            account_id = self.bank.validate_account_id(self.get_argument('account_id'))
            cursor = self.bank.conn.cursor()
            cursor.execute('SELECT * FROM accounts WHERE account_id = ?', (account_id,))
            account = cursor.fetchone()
            if account:
                self.write({
                    'account_id': account[0],
                    'customer_name': account[1],
                    'balance': account[2],
                    'account_type': account[3],
                    'created_at': account[4],
                })
            else:
                self.write_error_response(404, 'Account not found')
        except ValueError as e:
            self.write_error_response(400, str(e))
        except Exception:
            self.write_error_response(500, 'Internal server error')


class TransactionHandler(BaseBankHandler):

    def _optional_date_argument(self, name):
        value = self.get_argument(name, None)
        if value:
            value = self.bank.validate_date(value)
        return value

    @staticmethod
    def _serialize_transaction(row):
        return {
            'transaction_id': row[0],
            'amount': row[2],
            'type': row[3],
            'description': row[4],
            'timestamp': row[5],
        }

    def get(self):
        try:
            account_id = self.bank.validate_account_id(self.get_argument('account_id'))
            start_date = self._optional_date_argument('start_date')
            end_date = self._optional_date_argument('end_date')

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
            transactions = [self._serialize_transaction(row) for row in cursor.fetchall()]
            self.write({'transactions': transactions})
        except ValueError as e:
            self.write_error_response(400, str(e))
        except Exception:
            self.write_error_response(500, 'Internal server error')

    def _parse_amount(self, raw_amount):
        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError('Amount must be positive')
        except ValueError:
            raise ValueError('Invalid amount')
        return amount

    def _parse_transaction_request(self):
        data = json.loads(self.request.body)
        if not all(key in data for key in REQUIRED_TRANSACTION_FIELDS):
            raise ValueError('Missing required fields')
        account_id = self.bank.validate_account_id(str(data['account_id']))
        amount = self._parse_amount(data['amount'])
        if data['type'] not in TRANSACTION_TYPES:
            raise ValueError('Invalid transaction type')
        return data, account_id, amount

    def post(self):
        try:
            data, account_id, amount = self._parse_transaction_request()
            transaction_type = data['type']

            cursor = self.bank.conn.cursor()
            cursor.execute('SELECT 1 FROM accounts WHERE account_id = ?', (account_id,))
            if not cursor.fetchone():
                raise ValueError('Account not found')

            if transaction_type == 'withdrawal':
                cursor.execute('SELECT balance FROM accounts WHERE account_id = ?', (account_id,))
                balance = cursor.fetchone()[0]
                if balance < amount:
                    raise ValueError('Insufficient funds')

            cursor.execute(
                INSERT_TRANSACTION_SQL,
                (account_id, amount, transaction_type, data.get('description', '')),
            )
            cursor.execute(BALANCE_UPDATE_SQL[transaction_type], (amount, account_id))
            self.bank.conn.commit()
            self.write({'status': 'success', 'transaction_id': cursor.lastrowid})
        except ValueError as e:
            self.write_error_response(400, str(e))
        except Exception:
            self.bank.conn.rollback()
            self.write_error_response(500, 'Transaction failed')


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
