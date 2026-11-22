import json
import sqlite3
from datetime import datetime  # kept for module-level compatibility

import tornado.ioloop
import tornado.web


CREATE_ACCOUNTS_SQL = '''
    CREATE TABLE IF NOT EXISTS accounts (
        account_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        balance REAL DEFAULT 0,
        account_type TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
'''

CREATE_TRANSACTIONS_SQL = '''
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


class BankApplication:

    def __init__(self):
        self.conn = sqlite3.connect('bank.db')
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


class BankHandler(tornado.web.RequestHandler):
    """Base handler holding the shared bank application."""

    def initialize(self, bank_app):
        self.bank = bank_app

    def write_error_response(self, status, error):
        self.set_status(status)
        self.write({'error': str(error)})


class AccountHandler(BankHandler):

    @staticmethod
    def _serialize(account):
        return {
            'account_id': account[0],
            'customer_name': account[1],
            'balance': account[2],
            'account_type': account[3],
            'created_at': account[4],
        }

    def get(self):
        account_id = self.get_argument('account_id')
        cursor = self.bank.conn.cursor()
        try:
            # Parameterized query to avoid SQL injection.
            cursor.execute('SELECT * FROM accounts WHERE account_id = ?', (account_id,))
            account = cursor.fetchone()
            if account:
                self.write(self._serialize(account))
            else:
                self.write_error_response(404, 'Account not found')
        except Exception as e:
            self.write_error_response(500, e)


class TransactionHandler(BankHandler):

    @staticmethod
    def _serialize(row):
        return {
            'transaction_id': row[0],
            'amount': row[2],
            'type': row[3],
            'description': row[4],
            'timestamp': row[5],
        }

    def get(self):
        account_id = self.get_argument('account_id')
        start_date = self.get_argument('start_date', None)
        end_date = self.get_argument('end_date', None)

        query = 'SELECT * FROM transactions WHERE account_id = ?'
        params = [account_id]
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)

        cursor = self.bank.conn.cursor()
        try:
            cursor.execute(query, params)
            transactions = [self._serialize(row) for row in cursor.fetchall()]
            self.write({'transactions': transactions})
        except Exception as e:
            self.write_error_response(500, e)

    def post(self):
        try:
            data = json.loads(self.request.body)
            cursor = self.bank.conn.cursor()
            cursor.execute(
                INSERT_TRANSACTION_SQL,
                (data['account_id'], data['amount'], data['type'], data.get('description', '')),
            )
            sign = '+' if data['type'] == 'deposit' else '-'
            cursor.execute(
                f'UPDATE accounts SET balance = balance {sign} ? WHERE account_id = ?',
                (data['amount'], data['account_id']),
            )
            self.bank.conn.commit()
            self.write({'status': 'success', 'transaction_id': cursor.lastrowid})
        except Exception as e:
            self.write_error_response(400, e)


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
