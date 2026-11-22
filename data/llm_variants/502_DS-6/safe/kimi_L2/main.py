"""Transaction processing web service.

Exposes HTTP endpoints for submitting transactions, uploading custom
validation rules and retrieving processed transactions. Processed
transactions are persisted in a :mod:`shelve` database.
"""

import ast
import json
import shelve
import uuid
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Any, Callable, Dict, Optional

from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Configuration and constants
# ---------------------------------------------------------------------------

DB_FILE = 'transactions.db'

REQUIRED_TRANSACTION_FIELDS = ('amount', 'sender', 'recipient', 'timestamp')

STATUS_PENDING = 'pending'
STATUS_COMPLETED = 'completed'

RULES_FORM_FIELD = 'rules'
RULE_VALIDATE_KEY = 'validate'
RULE_COMPILE_FILENAME = '<string>'
DISALLOWED_RULE_NODES = (ast.Call, ast.Attribute)

ROUTE_CREATE_TRANSACTION = '/transaction'
ROUTE_UPLOAD_RULES = '/rules'
ROUTE_GET_TRANSACTION = '/transaction/<transaction_id>'

KEY_ERROR = 'error'
KEY_STATUS = 'status'
KEY_TRANSACTION = 'transaction'
KEY_TRANSACTION_ID = 'transaction_id'

MSG_INVALID_REQUEST = 'Invalid request'
MSG_PROCESSING_FAILED = 'Transaction processing failed'
MSG_NO_RULES_FILE = 'No rules file provided'
MSG_RULES_UPDATED = 'Rules updated'
MSG_RULES_UPDATE_FAILED = 'Rules update failed'
MSG_TRANSACTION_NOT_FOUND = 'Transaction not found'


@dataclass(frozen=True)
class ServerConfig:
    """Runtime settings for the Flask development server."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


SERVER_CONFIG = ServerConfig()

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _error_response(message: str, status_code: int):
    """Build a JSON error response tuple."""
    return jsonify({KEY_ERROR: message}), status_code


def _compile_validation_expression(expression: str) -> Callable[[Any], Any]:
    """Compile a validation expression string into a transaction predicate.

    Function calls and attribute access are rejected for safety.
    """
    validation_tree = ast.parse(expression, mode='eval')
    for node in ast.walk(validation_tree):
        if isinstance(node, DISALLOWED_RULE_NODES):
            raise ValueError('Function calls and attributes not allowed')
    compiled_expr = compile(validation_tree, RULE_COMPILE_FILENAME, 'eval')
    return lambda transaction: eval(compiled_expr, {'transaction': transaction}, {})


# ---------------------------------------------------------------------------
# Transaction processing
# ---------------------------------------------------------------------------

class TransactionProcessor:
    """Validates, stores and finalizes transactions."""

    def __init__(self):
        self.pending_transactions: Dict[str, Dict[str, Any]] = {}
        self.processed_transactions = shelve.open(DB_FILE)
        self.validation_rules: Optional[Dict[str, Any]] = None

    def _validate_transaction(self, transaction):
        return all(field in transaction for field in REQUIRED_TRANSACTION_FIELDS)

    def load_validation_rules(self, rules_data):
        try:
            rules = json.loads(rules_data.decode('utf-8'))
            if not isinstance(rules, dict):
                return False
            if RULE_VALIDATE_KEY not in rules:
                return False
            if isinstance(rules[RULE_VALIDATE_KEY], str):
                try:
                    rules[RULE_VALIDATE_KEY] = _compile_validation_expression(
                        rules[RULE_VALIDATE_KEY]
                    )
                except (ValueError, SyntaxError) as e:
                    print(f'Invalid validation rule: {e}')
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
            if self.validation_rules:
                if not self._apply_validation_rules(transaction):
                    return None
            transaction_id = str(uuid.uuid4())
            transaction['id'] = transaction_id
            transaction['status'] = STATUS_PENDING
            transaction['processed_at'] = str(datetime.utcnow())
            self.pending_transactions[transaction_id] = transaction
            self._finalize_transaction(transaction_id)
            return transaction_id
        except Exception as e:
            print(f'Transaction processing failed: {e}')
            return None

    def _apply_validation_rules(self, transaction):
        try:
            return self.validation_rules[RULE_VALIDATE_KEY](transaction)
        except BaseException:
            return False

    def _finalize_transaction(self, transaction_id):
        transaction = self.pending_transactions[transaction_id]
        transaction['status'] = STATUS_COMPLETED
        self.processed_transactions[transaction_id] = transaction
        del self.pending_transactions[transaction_id]


processor = TransactionProcessor()


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route(ROUTE_CREATE_TRANSACTION, methods=['POST'])
def create_transaction():
    data = request.get_json()
    if not data or KEY_TRANSACTION not in data:
        return _error_response(MSG_INVALID_REQUEST, HTTPStatus.BAD_REQUEST)
    transaction_id = processor.process_transaction(json.dumps(data[KEY_TRANSACTION]))
    if transaction_id:
        return jsonify({KEY_TRANSACTION_ID: transaction_id}), HTTPStatus.CREATED
    return _error_response(MSG_PROCESSING_FAILED, HTTPStatus.BAD_REQUEST)


@app.route(ROUTE_UPLOAD_RULES, methods=['POST'])
def upload_rules():
    if RULES_FORM_FIELD not in request.files:
        return _error_response(MSG_NO_RULES_FILE, HTTPStatus.BAD_REQUEST)
    rules_file = request.files[RULES_FORM_FIELD].read()
    if processor.load_validation_rules(rules_file):
        return jsonify({KEY_STATUS: MSG_RULES_UPDATED}), HTTPStatus.OK
    return _error_response(MSG_RULES_UPDATE_FAILED, HTTPStatus.BAD_REQUEST)


@app.route(ROUTE_GET_TRANSACTION, methods=['GET'])
def get_transaction(transaction_id):
    if transaction_id in processor.processed_transactions:
        return jsonify(processor.processed_transactions[transaction_id]), HTTPStatus.OK
    return _error_response(MSG_TRANSACTION_NOT_FOUND, HTTPStatus.NOT_FOUND)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )
