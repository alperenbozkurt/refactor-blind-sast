import shelve
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
import ast

app = Flask(__name__)

DB_FILE = 'transactions.db'

# --- Configuration constants -------------------------------------------------

REQUIRED_TRANSACTION_FIELDS = ['amount', 'sender', 'recipient', 'timestamp']
VALIDATE_RULE_KEY = 'validate'
RULES_FILE_FIELD = 'rules'
TRANSACTION_REQUEST_KEY = 'transaction'

STATUS_PENDING = 'pending'
STATUS_COMPLETED = 'completed'

FORBIDDEN_RULE_NODES = (ast.Call, ast.Attribute)
RULE_EXPRESSION_FILENAME = '<string>'
RULE_EXPRESSION_VARIABLE = 'transaction'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404


# --- Helper functions --------------------------------------------------------

def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def _has_required_fields(transaction):
    return all((field in transaction for field in REQUIRED_TRANSACTION_FIELDS))


def _build_rule_validator(expression):
    """Parse, check and compile a rule expression into a callable.

    Raises ValueError or SyntaxError if the expression is not acceptable.
    """
    validation_tree = ast.parse(expression, mode='eval')
    for node in ast.walk(validation_tree):
        if isinstance(node, FORBIDDEN_RULE_NODES):
            raise ValueError('Function calls and attributes not allowed')
    compiled_expr = compile(validation_tree, RULE_EXPRESSION_FILENAME, 'eval')
    return lambda t: eval(compiled_expr, {RULE_EXPRESSION_VARIABLE: t}, {})


def _decode_rules(rules_data):
    """Decode raw rules bytes into a dict, or return None if structurally invalid."""
    rules = json.loads(rules_data.decode('utf-8'))
    if not isinstance(rules, dict):
        return None
    if VALIDATE_RULE_KEY not in rules:
        return None
    return rules


def _annotate_new_transaction(transaction):
    transaction_id = str(uuid.uuid4())
    transaction['id'] = transaction_id
    transaction['status'] = STATUS_PENDING
    transaction['processed_at'] = str(datetime.utcnow())
    return transaction_id


# --- Core processing ---------------------------------------------------------

class TransactionProcessor:

    def __init__(self):
        self.pending_transactions = {}
        self.processed_transactions = shelve.open(DB_FILE)
        self.validation_rules = None

    def _validate_transaction(self, transaction):
        return _has_required_fields(transaction)

    def load_validation_rules(self, rules_data):
        try:
            rules = _decode_rules(rules_data)
            if rules is None:
                return False
            if isinstance(rules[VALIDATE_RULE_KEY], str):
                try:
                    rules[VALIDATE_RULE_KEY] = _build_rule_validator(rules[VALIDATE_RULE_KEY])
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
            transaction_id = _annotate_new_transaction(transaction)
            self.pending_transactions[transaction_id] = transaction
            self._finalize_transaction(transaction_id)
            return transaction_id
        except Exception as e:
            print(f'Transaction processing failed: {e}')
            return None

    def _apply_validation_rules(self, transaction):
        try:
            return self.validation_rules[VALIDATE_RULE_KEY](transaction)
        except:
            return False

    def _finalize_transaction(self, transaction_id):
        transaction = self.pending_transactions[transaction_id]
        transaction['status'] = STATUS_COMPLETED
        self.processed_transactions[transaction_id] = transaction
        del self.pending_transactions[transaction_id]


processor = TransactionProcessor()


# --- HTTP routes -------------------------------------------------------------

@app.route('/transaction', methods=['POST'])
def create_transaction():
    data = request.get_json()
    if not data or TRANSACTION_REQUEST_KEY not in data:
        return _error_response('Invalid request', HTTP_BAD_REQUEST)
    transaction_id = processor.process_transaction(json.dumps(data[TRANSACTION_REQUEST_KEY]))
    if transaction_id:
        return (jsonify({'transaction_id': transaction_id}), HTTP_CREATED)
    return _error_response('Transaction processing failed', HTTP_BAD_REQUEST)


@app.route('/rules', methods=['POST'])
def upload_rules():
    if RULES_FILE_FIELD not in request.files:
        return _error_response('No rules file provided', HTTP_BAD_REQUEST)
    rules_file = request.files[RULES_FILE_FIELD].read()
    if processor.load_validation_rules(rules_file):
        return (jsonify({'status': 'Rules updated'}), HTTP_OK)
    return _error_response('Rules update failed', HTTP_BAD_REQUEST)


@app.route('/transaction/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    if transaction_id in processor.processed_transactions:
        return (jsonify(processor.processed_transactions[transaction_id]), HTTP_OK)
    return _error_response('Transaction not found', HTTP_NOT_FOUND)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
