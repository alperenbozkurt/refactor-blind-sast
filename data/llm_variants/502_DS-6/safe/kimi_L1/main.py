"""Transaction processing service.

Exposes a small Flask API for submitting transactions, uploading custom
validation rules and retrieving processed transactions. Processed
transactions are persisted with shelve.
"""

import ast
import json
import shelve
import uuid
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)
DB_FILE = 'transactions.db'


class TransactionProcessor:
    """Validates, processes and stores transactions."""

    REQUIRED_FIELDS = ('amount', 'sender', 'recipient', 'timestamp')

    def __init__(self):
        self.pending_transactions = {}
        self.processed_transactions = shelve.open(DB_FILE)
        self.validation_rules = None

    def _validate_transaction(self, transaction):
        """Check that all required fields are present."""
        return all(field in transaction for field in self.REQUIRED_FIELDS)

    def load_validation_rules(self, rules_data):
        """Load validation rules from raw JSON data.

        Returns True when the rules were accepted, False otherwise.
        """
        try:
            rules = json.loads(rules_data.decode('utf-8'))
            if not isinstance(rules, dict):
                return False
            if 'validate' not in rules:
                return False
            if isinstance(rules['validate'], str):
                compiled_expr = self._compile_validation_expression(rules['validate'])
                if compiled_expr is None:
                    return False
                rules['validate'] = lambda t: eval(compiled_expr, {'transaction': t}, {})
            self.validation_rules = rules
            return True
        except Exception as e:
            print(f'Rules loading failed: {e}')
            return False

    @staticmethod
    def _compile_validation_expression(expression):
        """Compile a rule expression, rejecting calls and attribute access."""
        try:
            validation_tree = ast.parse(expression, mode='eval')
            for node in ast.walk(validation_tree):
                if isinstance(node, (ast.Call, ast.Attribute)):
                    raise ValueError('Function calls and attributes not allowed')
            return compile(validation_tree, '<string>', 'eval')
        except (ValueError, SyntaxError) as e:
            print(f'Invalid validation rule: {e}')
            return None

    def process_transaction(self, transaction_data):
        """Validate, store and finalize a transaction.

        Returns the new transaction id, or None when processing failed.
        """
        try:
            transaction = json.loads(transaction_data)
            if not self._validate_transaction(transaction):
                return None
            if self.validation_rules and not self._apply_validation_rules(transaction):
                return None
            transaction_id = self._store_pending_transaction(transaction)
            self._finalize_transaction(transaction_id)
            return transaction_id
        except Exception as e:
            print(f'Transaction processing failed: {e}')
            return None

    def _apply_validation_rules(self, transaction):
        """Run the configured validation callable against the transaction."""
        try:
            return self.validation_rules['validate'](transaction)
        except BaseException:
            # Deliberately broad: any rule failure rejects the transaction.
            return False

    def _store_pending_transaction(self, transaction):
        """Attach metadata to the transaction and store it as pending."""
        transaction_id = str(uuid.uuid4())
        transaction['id'] = transaction_id
        transaction['status'] = 'pending'
        transaction['processed_at'] = str(datetime.utcnow())
        self.pending_transactions[transaction_id] = transaction
        return transaction_id

    def _finalize_transaction(self, transaction_id):
        """Mark a pending transaction completed and persist it."""
        transaction = self.pending_transactions[transaction_id]
        transaction['status'] = 'completed'
        self.processed_transactions[transaction_id] = transaction
        del self.pending_transactions[transaction_id]


processor = TransactionProcessor()


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


@app.route('/transaction', methods=['POST'])
def create_transaction():
    """Process a transaction submitted as JSON."""
    data = request.get_json()
    if not data or 'transaction' not in data:
        return _error_response('Invalid request', 400)
    transaction_id = processor.process_transaction(json.dumps(data['transaction']))
    if transaction_id:
        return jsonify({'transaction_id': transaction_id}), 201
    return _error_response('Transaction processing failed', 400)


@app.route('/rules', methods=['POST'])
def upload_rules():
    """Replace the validation rules with an uploaded rules file."""
    if 'rules' not in request.files:
        return _error_response('No rules file provided', 400)
    rules_file = request.files['rules'].read()
    if processor.load_validation_rules(rules_file):
        return jsonify({'status': 'Rules updated'}), 200
    return _error_response('Rules update failed', 400)


@app.route('/transaction/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """Fetch a processed transaction by id."""
    if transaction_id in processor.processed_transactions:
        return jsonify(processor.processed_transactions[transaction_id]), 200
    return _error_response('Transaction not found', 404)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
