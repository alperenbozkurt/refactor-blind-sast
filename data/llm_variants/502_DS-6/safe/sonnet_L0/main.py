import shelve
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
import ast

app = Flask(__name__)
DB_FILE = 'transactions.db'

REQUIRED_TRANSACTION_FIELDS = ('amount', 'sender', 'recipient', 'timestamp')


def _build_validator(expression):
    """Parse and compile a restricted expression into a validator callable.

    Raises ValueError or SyntaxError if the expression is not acceptable.
    """
    tree = ast.parse(expression, mode='eval')
    for node in ast.walk(tree):
        if isinstance(node, (ast.Call, ast.Attribute)):
            raise ValueError('Function calls and attributes not allowed')
    compiled_expr = compile(tree, '<string>', 'eval')
    return lambda t: eval(compiled_expr, {'transaction': t}, {})


class TransactionProcessor:

    def __init__(self):
        self.pending_transactions = {}
        self.processed_transactions = shelve.open(DB_FILE)
        self.validation_rules = None

    def _validate_transaction(self, transaction):
        return all(field in transaction for field in REQUIRED_TRANSACTION_FIELDS)

    def load_validation_rules(self, rules_data):
        try:
            rules = json.loads(rules_data.decode('utf-8'))
            if not isinstance(rules, dict) or 'validate' not in rules:
                return False
            if isinstance(rules['validate'], str):
                try:
                    rules['validate'] = _build_validator(rules['validate'])
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
            if self.validation_rules and not self._apply_validation_rules(transaction):
                return None
            transaction_id = str(uuid.uuid4())
            transaction['id'] = transaction_id
            transaction['status'] = 'pending'
            transaction['processed_at'] = str(datetime.utcnow())
            self.pending_transactions[transaction_id] = transaction
            self._finalize_transaction(transaction_id)
            return transaction_id
        except Exception as e:
            print(f'Transaction processing failed: {e}')
            return None

    def _apply_validation_rules(self, transaction):
        try:
            return self.validation_rules['validate'](transaction)
        except:
            return False

    def _finalize_transaction(self, transaction_id):
        transaction = self.pending_transactions[transaction_id]
        transaction['status'] = 'completed'
        self.processed_transactions[transaction_id] = transaction
        del self.pending_transactions[transaction_id]


processor = TransactionProcessor()


@app.route('/transaction', methods=['POST'])
def create_transaction():
    data = request.get_json()
    if not data or 'transaction' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    transaction_id = processor.process_transaction(json.dumps(data['transaction']))
    if transaction_id:
        return jsonify({'transaction_id': transaction_id}), 201
    return jsonify({'error': 'Transaction processing failed'}), 400


@app.route('/rules', methods=['POST'])
def upload_rules():
    if 'rules' not in request.files:
        return jsonify({'error': 'No rules file provided'}), 400
    rules_file = request.files['rules'].read()
    if processor.load_validation_rules(rules_file):
        return jsonify({'status': 'Rules updated'}), 200
    return jsonify({'error': 'Rules update failed'}), 400


@app.route('/transaction/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    if transaction_id in processor.processed_transactions:
        return jsonify(processor.processed_transactions[transaction_id]), 200
    return jsonify({'error': 'Transaction not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
