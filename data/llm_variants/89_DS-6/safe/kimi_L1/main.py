import json
import re
import sqlite3
from datetime import datetime

import tornado.ioloop
import tornado.web


class BankApplication:
    """Owns the SQLite connection and the shared validation helpers."""

    CREATE_ACCOUNTS_TABLE = """
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            balance REAL DEFAULT 0,
            account_type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    CREATE_TRANSACTIONS_TABLE = """
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

    INSERT_ACCOUNT = (
        'INSERT INTO accounts (customer_name, balance, account_type) '
        'VALUES (?, ?, ?)'
    )
    INSERT_TRANSACTION = (
        'INSERT INTO transactions '
        '(account_id, amount, transaction_type, description) '
        'VALUES (?, ?, ?, ?)'
    )
    INCREASE_BALANCE = (
        'UPDATE accounts SET balance = balance + ? WHERE account_id = ?'
    )
    DECREASE_BALANCE = (
        'UPDATE accounts SET balance = balance - ? WHERE account_id = ?'
    )

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

    DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    def __init__(self):
        self.conn = sqlite3.connect('bank.db')
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(self.CREATE_ACCOUNTS_TABLE)
        cursor.execute(self.CREATE_TRANSACTIONS_TABLE)
        cursor.execute('SELECT COUNT(*) FROM accounts')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(self.INSERT_ACCOUNT, self.SEED_ACCOUNTS)
            cursor.executemany(self.INSERT_TRANSACTION, self.SEED_TRANSACTIONS)
        self.conn.commit()

    def validate_account_id(self, account_id):
        if not account_id or not account_id.isdigit():
            raise ValueError('Invalid account ID')
        return int(account_id)

    def validate_date(self, date_str):
        if not self.DATE_PATTERN.match(date_str):
            raise ValueError('Invalid date format. Use YYYY-MM-DD')
        return date_str


class _BankRequestHandler(tornado.web.RequestHandler):
    """Common plumbing shared by the bank request handlers."""

    def initialize(self, bank_app):
        self.bank = bank_app

    def _write_error(self, status, message):
        self.set_status(status)
        self.write({'error': message})


class AccountHandler(_BankRequestHandler):

    SELECT_ACCOUNT = 'SELECT * FROM accounts WHERE account_id = ?'

    @staticmethod
    def _account_to_dict(account):
        return {
            'account_id': account[0],
            'customer_name': account[1],
            'balance': account[2],
            'account_type': account[3],
            'created_at': account[4],
        }

    def get(self):
        try:
            account_id = self.bank.validate_account_id(
                self.get_argument('account_id')
            )
            cursor = self.bank.conn.cursor()
            cursor.execute(self.SELECT_ACCOUNT, (account_id,))
            account = cursor.fetchone()
            if account:
                self.write(self._account_to_dict(account))
            else:
                self._write_error(404, 'Account not found')
        except ValueError as e:
            self._write_error(400, str(e))
        except Exception:
            self._write_error(500, 'Internal server error')


class TransactionHandler(_BankRequestHandler):

    REQUIRED_FIELDS = ('account_id', 'amount', 'type')
    VALID_TYPES = ('deposit', 'withdrawal')
    SELECT_TRANSACTIONS = 'SELECT * FROM transactions WHERE account_id = ?'

    def get(self):
        try:
            account_id = self.bank.validate_account_id(
                self.get_argument('account_id')
            )
            start_date = self.get_argument('start_date', None)
            end_date = self.get_argument('end_date', None)
            if start_date:
                start_date = self.bank.validate_date(start_date)
            if end_date:
                end_date = self.bank.validate_date(end_date)
            query, params = self._build_history_query(
                account_id, start_date, end_date
            )
            cursor = self.bank.conn.cursor()
            cursor.execute(query, params)
            transactions = [
                self._transaction_to_dict(row) for row in cursor.fetchall()
            ]
            self.write({'transactions': transactions})
        except ValueError as e:
            self._write_error(400, str(e))
        except Exception:
            self._write_error(500, 'Internal server error')

    def post(self):
        try:
            data = json.loads(self.request.body)
            account_id, amount, trans_type, description = (
                self._parse_transaction(data)
            )
            cursor = self.bank.conn.cursor()
            self._check_account_exists(cursor, account_id)
            if trans_type == 'withdrawal':
                self._check_sufficient_funds(cursor, account_id, amount)
            cursor.execute(
                self.bank.INSERT_TRANSACTION,
                (account_id, amount, trans_type, description),
            )
            if trans_type == 'deposit':
                cursor.execute(
                    self.bank.INCREASE_BALANCE, (amount, account_id)
                )
            else:
                cursor.execute(
                    self.bank.DECREASE_BALANCE, (amount, account_id)
                )
            self.bank.conn.commit()
            self.write({'status': 'success', 'transaction_id': cursor.lastrowid})
        except ValueError as e:
            self._write_error(400, str(e))
        except Exception:
            self.bank.conn.rollback()
            self._write_error(500, 'Transaction failed')

    def _build_history_query(self, account_id, start_date, end_date):
        query = self.SELECT_TRANSACTIONS
        params = [account_id]
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        return query, params

    @staticmethod
    def _transaction_to_dict(row):
        return {
            'transaction_id': row[0],
            'amount': row[2],
            'type': row[3],
            'description': row[4],
            'timestamp': row[5],
        }

    def _parse_transaction(self, data):
        if not all(key in data for key in self.REQUIRED_FIELDS):
            raise ValueError('Missing required fields')
        account_id = self.bank.validate_account_id(str(data['account_id']))
        amount = self._parse_amount(data['amount'])
        if data['type'] not in self.VALID_TYPES:
            raise ValueError('Invalid transaction type')
        return account_id, amount, data['type'], data.get('description', '')

    @staticmethod
    def _parse_amount(value):
        try:
            amount = float(value)
            if amount <= 0:
                # Caught below, so the client always sees 'Invalid amount'.
                raise ValueError('Amount must be positive')
        except ValueError:
            raise ValueError('Invalid amount')
        return amount

    @staticmethod
    def _check_account_exists(cursor, account_id):
        cursor.execute(
            'SELECT 1 FROM accounts WHERE account_id = ?', (account_id,)
        )
        if not cursor.fetchone():
            raise ValueError('Account not found')

    @staticmethod
    def _check_sufficient_funds(cursor, account_id, amount):
        cursor.execute(
            'SELECT balance FROM accounts WHERE account_id = ?', (account_id,)
        )
        balance = cursor.fetchone()[0]
        if balance < amount:
            raise ValueError('Insufficient funds')


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
