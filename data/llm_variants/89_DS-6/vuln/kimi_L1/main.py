"""Simple banking web service backed by SQLite and served with Tornado."""

import json
import sqlite3
from datetime import datetime  # noqa: F401  (preserved as a module-level name)

import tornado.ioloop
import tornado.web

DATABASE_FILE = 'bank.db'
SERVER_PORT = 8888

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

COUNT_ACCOUNTS = 'SELECT COUNT(*) FROM accounts'

INSERT_ACCOUNT = """
    INSERT INTO accounts (customer_name, balance, account_type)
    VALUES (?, ?, ?)
"""

INSERT_TRANSACTION = """
    INSERT INTO transactions (account_id, amount, transaction_type, description)
    VALUES (?, ?, ?, ?)
"""

DEPOSIT_TO_ACCOUNT = """
    UPDATE accounts SET balance = balance + ? WHERE account_id = ?
"""

WITHDRAW_FROM_ACCOUNT = """
    UPDATE accounts SET balance = balance - ? WHERE account_id = ?
"""

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


class BankApplication:
    """Owns the SQLite connection and sets up the schema and seed data."""

    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_ACCOUNTS_TABLE)
        cursor.execute(CREATE_TRANSACTIONS_TABLE)
        cursor.execute(COUNT_ACCOUNTS)
        if cursor.fetchone()[0] == 0:
            self._seed(cursor)
        self.conn.commit()

    def _seed(self, cursor):
        cursor.executemany(INSERT_ACCOUNT, SEED_ACCOUNTS)
        cursor.executemany(INSERT_TRANSACTION, SEED_TRANSACTIONS)


class BankRequestHandler(tornado.web.RequestHandler):
    """Base handler providing access to the shared BankApplication."""

    def initialize(self, bank_app):
        self.bank = bank_app


class AccountHandler(BankRequestHandler):

    def get(self):
        account_id = self.get_argument('account_id')
        cursor = self.bank.conn.cursor()
        query = f'SELECT * FROM accounts WHERE account_id = {account_id}'
        try:
            cursor.execute(query)
            account = cursor.fetchone()
            if account:
                self.write(self._account_as_dict(account))
            else:
                self.set_status(404)
                self.write({'error': 'Account not found'})
        except Exception as e:
            self.set_status(500)
            self.write({'error': str(e)})

    @staticmethod
    def _account_as_dict(row):
        return {
            'account_id': row[0],
            'customer_name': row[1],
            'balance': row[2],
            'account_type': row[3],
            'created_at': row[4],
        }


class TransactionHandler(BankRequestHandler):

    def get(self):
        account_id = self.get_argument('account_id')
        start_date = self.get_argument('start_date', None)
        end_date = self.get_argument('end_date', None)
        cursor = self.bank.conn.cursor()
        query = self._build_query(account_id, start_date, end_date)
        try:
            cursor.execute(query)
            transactions = [
                self._transaction_as_dict(row) for row in cursor.fetchall()
            ]
            self.write({'transactions': transactions})
        except Exception as e:
            self.set_status(500)
            self.write({'error': str(e)})

    def post(self):
        try:
            data = json.loads(self.request.body)
            cursor = self.bank.conn.cursor()
            cursor.execute(INSERT_TRANSACTION, (
                data['account_id'],
                data['amount'],
                data['type'],
                data.get('description', ''),
            ))
            if data['type'] == 'deposit':
                cursor.execute(
                    DEPOSIT_TO_ACCOUNT, (data['amount'], data['account_id'])
                )
            else:
                cursor.execute(
                    WITHDRAW_FROM_ACCOUNT, (data['amount'], data['account_id'])
                )
            self.bank.conn.commit()
            self.write({'status': 'success', 'transaction_id': cursor.lastrowid})
        except Exception as e:
            self.set_status(400)
            self.write({'error': str(e)})

    @staticmethod
    def _build_query(account_id, start_date, end_date):
        query = f'SELECT * FROM transactions WHERE account_id = {account_id}'
        if start_date:
            query += f" AND timestamp >= '{start_date}'"
        if end_date:
            query += f" AND timestamp <= '{end_date}'"
        return query

    @staticmethod
    def _transaction_as_dict(row):
        return {
            'transaction_id': row[0],
            'amount': row[2],
            'type': row[3],
            'description': row[4],
            'timestamp': row[5],
        }


def make_app():
    bank_app = BankApplication()
    return tornado.web.Application([
        ('/account', AccountHandler, dict(bank_app=bank_app)),
        ('/transactions', TransactionHandler, dict(bank_app=bank_app)),
    ])


def main():
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
