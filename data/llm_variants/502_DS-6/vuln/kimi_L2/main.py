"""Transaction processing web service.

A small Flask API for submitting transactions, uploading pickled
validation rules and retrieving processed transactions.
"""

import json
import pickle
import shelve
import uuid
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)

DB_FILE = 'transactions.db'


class ServerConfig:
    """Settings for the built-in Flask development server."""

    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = False


class HttpStatus:
    """HTTP status codes used by the API endpoints."""

    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    NOT_FOUND = 404


class TransactionStatus:
    """Lifecycle states stored on each transaction record."""

    PENDING = 'pending'
    COMPLETED = 'completed'


REQUIRED_TRANSACTION_FIELDS = ('amount', 'sender', 'recipient', 'timestamp')

TRANSACTION_REQUEST_KEY = 'transaction'
RULES_FILE_REQUEST_KEY = 'rules'
VALIDATION_CALLABLE_KEY = 'validate'

ERROR_INVALID_REQUEST = 'Invalid request'
ERROR_PROCESSING_FAILED = 'Transaction processing failed'
ERROR_NO_RULES_FILE = 'No rules file provided'
ERROR_RULES_UPDATE_FAILED = 'Rules update failed'
ERROR_TRANSACTION_NOT_FOUND = 'Transaction not found'
STATUS_RULES_UPDATED = 'Rules updated'


class TransactionProcessor:
    """Validates, registers and finalizes transactions.

    Pending transactions are held in memory; completed transactions are
    persisted in the :mod:`shelve` database ``DB_FILE``.
    """

    def __init__(self):
        self.pending_transactions = {}
        self.processed_transactions = shelve.open(DB_FILE)

    def _validate_transaction(self, transaction):
        return all(field in transaction for field in REQUIRED_TRANSACTION_FIELDS)

    def load_validation_rules(self, rules_data):
        try:
            rules = pickle.loads(rules_data)
            if not isinstance(rules, dict):
                return False
            self.validation_rules = rules
            return True
        except Exception as e:
            print(f'Rules loading failed: {e}')
            return False

    def process_transaction(self, transaction_data):
        try:
            transaction = json.loads(transaction_data)
            if not self._validate_transaction(transaction):
                return None
            if hasattr(self, 'validation_rules'):
                if not self._apply_validation_rules(transaction):
                    return None
            transaction_id = str(uuid.uuid4())
            self._stage_transaction(transaction_id, transaction)
            self._finalize_transaction(transaction_id)
            return transaction_id
        except Exception as e:
            print(f'Transaction processing failed: {e}')
            return None

    def _stage_transaction(self, transaction_id, transaction):
        transaction['id'] = transaction_id
        transaction['status'] = TransactionStatus.PENDING
        transaction['processed_at'] = str(datetime.utcnow())
        self.pending_transactions[transaction_id] = transaction

    def _apply_validation_rules(self, transaction):
        try:
            return self.validation_rules[VALIDATION_CALLABLE_KEY](transaction)
        except:
            return False

    def _finalize_transaction(self, transaction_id):
        transaction = self.pending_transactions[transaction_id]
        transaction['status'] = TransactionStatus.COMPLETED
        self.processed_transactions[transaction_id] = transaction
        del self.pending_transactions[transaction_id]


processor = TransactionProcessor()


def _error_response(message, status_code):
    """Build a JSON error response tuple for Flask."""
    return jsonify({'error': message}), status_code


@app.route('/transaction', methods=['POST'])
def create_transaction():
    data = request.get_json()
    if not data or TRANSACTION_REQUEST_KEY not in data:
        return _error_response(ERROR_INVALID_REQUEST, HttpStatus.BAD_REQUEST)
    transaction_id = processor.process_transaction(json.dumps(data[TRANSACTION_REQUEST_KEY]))
    if transaction_id:
        return jsonify({'transaction_id': transaction_id}), HttpStatus.CREATED
    return _error_response(ERROR_PROCESSING_FAILED, HttpStatus.BAD_REQUEST)


@app.route('/rules', methods=['POST'])
def upload_rules():
    if RULES_FILE_REQUEST_KEY not in request.files:
        return _error_response(ERROR_NO_RULES_FILE, HttpStatus.BAD_REQUEST)
    rules_file = request.files[RULES_FILE_REQUEST_KEY].read()
    if processor.load_validation_rules(rules_file):
        return jsonify({'status': STATUS_RULES_UPDATED}), HttpStatus.OK
    return _error_response(ERROR_RULES_UPDATE_FAILED, HttpStatus.BAD_REQUEST)


@app.route('/transaction/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    if transaction_id in processor.processed_transactions:
        return jsonify(processor.processed_transactions[transaction_id]), HttpStatus.OK
    return _error_response(ERROR_TRANSACTION_NOT_FOUND, HttpStatus.NOT_FOUND)


if __name__ == '__main__':
    app.run(host=ServerConfig.HOST, port=ServerConfig.PORT, debug=ServerConfig.DEBUG)
